from pytoniq import Address, begin_cell, LiteBalancer, WalletV4R2, LiteClient
import asyncio
from pytoniq import Contract
from pytoniq_core import Slice, Cell, boc, MessageAny, Transaction, TransactionError, TvmBitarray
import json
import pandas as pd


provider = LiteBalancer.from_mainnet_config(4)
await provider.start_up()

def unroll_cell(cell):
    results = []
    slice = cell.begin_parse()
    
    while len(slice.bits) >= 32:
        result = {}

        # Extract opcode
        opcode = hex(slice.load_uint(32))
        result['opcode'] = opcode

        # Check if the opcode is known and apply corresponding parsing technique
        if opcode == '0x7362d09c':  # Jetton Transfer Notification
            result.update(jetton_transfer_notif(slice))
        
        else:
            result['message'] = 'Unknown opcode, skipping further parsing'

        results.append(result)

    refs = slice.refs
    if refs:
        for ref in refs:
            results.extend(unroll_cell(ref))  # Recursively unroll and collect results

    return results


def decompose_msg(msg):
    try:
        # Decompose a single message (in_msg or out_msg)
        return {
            'src': msg.info.src.to_str(1, 1, 1),
            'dest': msg.info.dest.to_str(1, 1, 1),
            'coins': msg.info.value.grams / 1e9,
            'body': unroll_cell(msg.body)  # Unroll the body cell
        }
    except Exception as e:
        # Handle exceptions by logging or returning a placeholder
        return {"error": str(e)}

def decompose_tx(tx):
    try:
        # Prepare the dictionary to hold transaction details
        tx_dict = {
            'in_msg': decompose_msg(tx.in_msg),  # Process the incoming message
            'out_msgs': [decompose_msg(msg) for msg in tx.out_msgs if msg],  # Process all outgoing messages
            'tx_cell': unroll_cell(tx.cell),  # Unroll the main transaction cell
            'cell_hash': tx.cell.hash
        }
        return tx_dict
    except Exception as e:
        # Return a dictionary indicating an error with the transaction parsing
        return {'error': f"Failed to decompose transaction: {str(e)}"}
