# pytontx
Transaction decomposer for TON blockchain written in Python using pytoniq 


# TON Blockchain Transaction Parser

This project provides a set of Python scripts designed to parse and decompose transactions on the TON (Telegram Open Network) blockchain. It includes functionality to recursively unroll cells within the transactions and visualize transaction data, helping users to analyze and understand transaction flows and contents.

## Features

- **Transaction Decomposition**: Break down transactions into their constituent parts, including source, destination, and transferred coins.
- **Cell Unrolling**: Recursively parse the cells within transactions to extract and interpret stored data and operations.
- **Error Handling**: Robust error management to gracefully handle and log issues during the transaction parsing process.

## Requirements

- Python 3.7+
- `pytoniq` and `pytoniq_core` packages for interacting with TON blockchain data.

