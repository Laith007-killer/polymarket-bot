import os, requests, json
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

load_dotenv("/Users/laithsassistant/CLAUDE/bots/.env", override=True)

TARGET_ADDRESS = "0x492442eab586f242b53bda933fd5de859c8a3782"
FUNDER_ADDRESS = "0x35ebbf25efec57f68b0ef737794987ad71742848"
PRIVATE_KEY = os.environ["POLYMARKET_KEY"]
SIGNATURE_TYPE = 1
BET_AMOUNT = 2.0
DRY_RUN = False

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
PROFILE_API = "https://gamma-api.polymarket.com"
LOG_FILE = "/Users/laithsassistant/CLAUDE/bots/trades_log.json"

def log_trade(**kwargs):
    try:
        kwargs["timestamp"] = datetime.utcnow().isoformat() + "Z"
        kwargs["target_wallet"] = TARGET_ADDRESS
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        logs.append(kwargs)
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except:
        pass

def get_profile_name(addr):
    r = requests.get(f"{PROFILE_API}/public-profile", params={"address": addr})
    r.raise_for_status()
    p = r.json()
    return p.get("name") or p.get("pseudonym") or addr[:10] + "..."

def get_positions(addr):
    r = requests.get(f"{DATA_API}/positions", params={"user": addr, "sizeThreshold": 0})
    r.raise_for_status()
    return r.json()

def get_latest_bet(addr):
    r = requests.get(f"{DATA_API}/activity", params={"user": addr, "limit": 20})
    r.raise_for_status()
    for a in r.json():
        if a.get("type") == "TRADE" and a.get("side") == "BUY":
            return a
    return None

def already_has_position(positions, conditionId, outcomeIndex):
    target = f"{conditionId}_{outcomeIndex}"
    return target in {f"{p['conditionId']}_{p['outcomeIndex']}" for p in positions}

def get_clob_client():
    client = ClobClient(CLOB_API, key=PRIVATE_KEY, chain_id=137, signature_type=SIGNATURE_TYPE, funder=FUNDER_ADDRESS)
    client.set_api_creds(client.derive_api_key())
    return client

def place_bet(client, token_id, amount):
    order = MarketOrderArgs(token_id=token_id, amount=amount, side=BUY, order_type=OrderType.FOK)
    client.post_order(client.create_market_order(order), OrderType.FOK)

def main():
    latest = get_latest_bet(TARGET_ADDRESS)
    if not latest:
        print("No recent bets found.")
        log_trade(action="NO_TRADE_FOUND", market=None, outcome=None, entry_price=None, amount=BET_AMOUNT, condition_id=None, outcome_index=None)
        return

    print(f"Found: {latest['title'][:50]}")
    print(f"Position: {latest['outcome']} @ {latest['price']*100:.1f}c")

    my_positions = get_positions(FUNDER_ADDRESS)
    if already_has_position(my_positions, latest["conditionId"], latest["outcomeIndex"]):
        print("Already in this market. Nothing to do!")
        log_trade(action="SKIP_ALREADY_IN", market=latest["title"], outcome=latest["outcome"], entry_price=latest["price"], amount=BET_AMOUNT, condition_id=latest["conditionId"], outcome_index=latest["outcomeIndex"])
        return

    print(f"Placing bet: ${BET_AMOUNT:.2f} of {latest['outcome']}")
    if DRY_RUN:
        print(f"DRY RUN - would buy ${BET_AMOUNT:.2f} of {latest['outcome']}")
    else:
        place_bet(get_clob_client(), latest["asset"], BET_AMOUNT)
        print(f"Done! Bought ${BET_AMOUNT:.2f} of {latest['outcome']}")
    log_trade(action="BUY", market=latest["title"], outcome=latest["outcome"], entry_price=latest["price"], amount=BET_AMOUNT, condition_id=latest["conditionId"], outcome_index=latest["outcomeIndex"])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        log_trade(action="ERROR", error=str(e), market=None, outcome=None, entry_price=None, amount=BET_AMOUNT, condition_id=None, outcome_index=None)
