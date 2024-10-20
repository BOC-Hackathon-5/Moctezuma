from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from datetime import datetime
from solders. rpc. responses import GetTransactionResp
from solders.keypair import Keypair
from spl.token.instructions import transfer_checked, TransferCheckedParams
import solana.transaction
import solana.exceptions
import base58

digital_eur_mint_account_pub_key = Pubkey.from_string("HUfkqRBzq8cz3RdV98HUysK6GvEzNX37LPaEreNGpump")
digital_asset_mint_account_pub_key = Pubkey.from_string("Hf52GajTATNHvt8PNgh1U8tTWSFXPf3uaUygH3kNpump")

# don't worry this is temporary
quick_node_api_key = "QN_ced12264f48445f6b35ed940ab9f1a04"

class Transaction:
    def __init__(
            self,
            signature: str,
            timestamp: datetime,
            sender: Pubkey,
            receiver: Pubkey,
            amount: float,
            token: str,
    ):
        self.signature = signature
        self.timestamp = timestamp
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.token = token

    def __str__(self):
        return f"{self.signature} {self.timestamp} {self.sender} {self.receiver} {self.amount} {self.token}"

def parse_transaction(signature: str, transaction_dto: GetTransactionResp, token: str) -> Transaction:
    if transaction_dto.value.transaction.meta.err is not None:
        return None

    sender_post_amount = 0
    sender_pre_amount = 0
    receiver_post_amount = 0
    receiver_pre_amount = 0

    try:
        sender_post_amount = transaction_dto.value.transaction.meta.post_token_balances[0].ui_token_amount.ui_amount
        sender = transaction_dto.value.transaction.meta.post_token_balances[0].owner
        if sender_post_amount is None:
            sender_post_amount = 0
    except IndexError:
        pass

    try:
        receiver_post_amount = transaction_dto.value.transaction.meta.post_token_balances[1].ui_token_amount.ui_amount
        receiver = transaction_dto.value.transaction.meta.post_token_balances[1].owner
        if receiver_post_amount is None:
            receiver_post_amount = 0
    except IndexError:
        pass

    try:
        sender_pre_amount = transaction_dto.value.transaction.meta.pre_token_balances[0].ui_token_amount.ui_amount
        sender = transaction_dto.value.transaction.meta.post_token_balances[0].owner
        if sender_pre_amount is None:
            sender_pre_amount = 0
    except IndexError:
        pass

    try:
        receiver_pre_amount = transaction_dto.value.transaction.meta.pre_token_balances[1].ui_token_amount.ui_amount
        receiver = transaction_dto.value.transaction.meta.post_token_balances[1].owner
        if receiver_pre_amount is None:
            receiver_pre_amount = 0
    except IndexError:
        pass

    return Transaction(
        signature=signature,
        timestamp=datetime.fromtimestamp(transaction_dto.value.block_time),
        sender=sender,
        receiver=receiver,
        amount=sender_post_amount-receiver_pre_amount,
        token=token,
    )

class Account:
    solana_client = Client("https://api.mainnet-beta.solana.com")
    solana_quicknode_client = Client(f"https://black-orbital-seed.solana-mainnet.quiknode.pro/4d24d70dcd4996eccdae1363777557d4a1fb83e1/{quick_node_api_key}")

    def __init__(self, pub_key: Pubkey, private_key, mint_account_pub_key: Pubkey):
        self.pub_key = pub_key
        self.private_key = None
        if private_key is not None:
            self.private_key = private_key
        self.mint_account_pub_key = mint_account_pub_key
        self.account = self.solana_client.get_token_accounts_by_owner(pub_key, TokenAccountOpts(mint=mint_account_pub_key)).value[0].pubkey

    @property
    def get_balance(self):
        try:
            return self.solana_client.get_token_account_balance(self.account).value.ui_amount
        except AttributeError:
            return -1

    @property
    def get_pub_key(self)->Pubkey:
        return self.pub_key

    @property
    def get_account(self)->Pubkey:
        return self.account

    @property
    def get_transactions(self)->list[Transaction]:
        transactions = []

        try:
            signatures = self.solana_client.get_signatures_for_address(self.account).value
        except solana.exceptions.SolanaRpcException:
            return transactions

        for signature in signatures:
            transaction_dto = self.solana_quicknode_client.get_transaction(signature.signature, "jsonParsed", max_supported_transaction_version=0)

            if self.mint_account_pub_key == digital_eur_mint_account_pub_key:
                token = "DEUR"
            elif self.mint_account_pub_key == digital_asset_mint_account_pub_key:
                token = "DA"
            else:
                token = ""

            parsed_transaction = parse_transaction(str(signature.signature), transaction_dto, token)
            if parsed_transaction is not None:
                transactions.append(parsed_transaction)

        return sorted(transactions, key=lambda x: x.timestamp, reverse=True)

    def send_token(self, receiver: Pubkey, amount: int):
        if self.private_key is None:
            raise Exception("Private key is not set")

        keypair = Keypair.from_base58_string(self.private_key)

        transaction = self.solana_client.send_transaction(solana.transaction.Transaction().add(
            transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=self.account,
                    mint=self.mint_account_pub_key,
                    dest=receiver,
                    owner=self.pub_key,
                    amount=amount * 1_000_000,
                    decimals=6,
                    signers=[],
                )
            )
        ), keypair)
        return self.solana_client.confirm_transaction(transaction.value, sleep_seconds=2)

def create_new_account(mint_account_pub_key: Pubkey)->Account:
    wallet = Keypair()
    private_key = base58.b58encode(wallet.secret() + base58.b58decode(str(wallet.pubkey()))).decode('utf-8')
    with open("wallet.csv", "a") as f:
        f.write(f"{wallet.pubkey()} {private_key}\n")

    return Account(wallet.pubkey(), private_key, mint_account_pub_key)

def main():
    # cba = Account(Pubkey.from_string("H4vETeFN6jggp7DeXH6YjoNvQ1NCL4penqv6W9c7MDDE"), "6tyPbY7LA3Rt7DMJ1zyC1kfMpUpu8VVFm5ENHqjd6A7btCvPig1bGH9W88JUq9pVeCDmxHAkwJVivcvZ7odUJ6Q", digital_eur_mint_account_pub_key)
    # print(cba.get_balance)
    # print(cba.send_token(Pubkey.from_string("GY26NdnY6MEzJC4KA4dpCndAHdNLvjrF6BmoHEYk1XF3"), 666))
    # print(cba.get_balance)

    daa = Account(Pubkey.from_string("FnWbZSeL7HUSFXH8g1hKSoKD9aoT5oBStTtiDrbLQoTK"), None, digital_eur_mint_account_pub_key)
    print(daa.get_balance)
    for tr in daa.get_transactions:
        print(tr)

main()
