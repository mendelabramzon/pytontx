# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncio
import json
from pytoniq import LiteBalancer, Address
from pytoniq_core import Transaction

OPCODES = {
    "Transfer": 0x0ec3c86d,
}

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def parse_transfer(cell_slice):
    try:
        opcode = cell_slice.load_uint(32)
        query_id = cell_slice.load_uint(64)
        amount = cell_slice.load_coins()
        recipient = cell_slice.load_address()
        return {
            "Type": "Transfer" if opcode == OPCODES["Transfer"] else f"Unknown ({hex(opcode)})",
            "Query ID": query_id,
            "Amount": amount,
            "Recipient": recipient.to_str(1, 1, 0) if recipient else "None"
        }
    except Exception as e:
        return {"Error": str(e)}

async def get_interacting_wallets(contract_address: str):
    async with LiteBalancer.from_mainnet_config(8) as client:
        address = Address(contract_address)
        transactions = await client.get_transactions(address=address, count=10)

        interacting_wallets = {}
        transaction_details = []

        for transaction in transactions:
            # Process incoming message
            if transaction.in_msg:
                in_msg = transaction.in_msg
                src = in_msg.info.src.to_str(1, 1, 0) if in_msg.info.src else "None"
                if src != "None" and src != contract_address:
                    if src not in interacting_wallets:
                        interacting_wallets[src] = {"in": 0, "out": 0}
                    interacting_wallets[src]["in"] += 1

                try:
                    cell_slice = in_msg.body.begin_parse()
                    parsed_data = parse_transfer(cell_slice)
                    transaction_details.append({
                        "direction": "Incoming",
                        "address": src,
                        "data": parsed_data
                    })
                except Exception as e:
                    transaction_details.append({
                        "direction": "Incoming",
                        "address": src,
                        "data": {"Error": str(e)}
                    })

            # Process outgoing messages
            if transaction.out_msgs:
                for out_msg in transaction.out_msgs:
                    try:
                        dest = out_msg.info.dest.to_str(1, 1, 0) if out_msg.info.dest else "None"
                        if dest != "None" and dest != contract_address:
                            if dest not in interacting_wallets:
                                interacting_wallets[dest] = {"in": 0, "out": 0}
                            interacting_wallets[dest]["out"] += 1

                        cell_slice = out_msg.body.begin_parse()
                        parsed_data = parse_transfer(cell_slice)
                        transaction_details.append({
                            "direction": "Outgoing",
                            "address": dest,
                            "data": parsed_data
                        })
                    except Exception as e:
                        transaction_details.append({
                            "direction": "Outgoing",
                            "address": dest,
                            "data": {"Error": str(e)}
                        })

        return interacting_wallets, transaction_details

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/dashboard", response_class=HTMLResponse)
async def show_dashboard(request: Request, contract_address: str = Form(...)):
    wallets, transaction_details = await get_interacting_wallets(contract_address)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "contract_address": contract_address,
        "wallets": wallets,
        "transaction_details": transaction_details
    })