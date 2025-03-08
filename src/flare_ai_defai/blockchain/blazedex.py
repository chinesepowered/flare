"""
BlazeSwap Integration Module

This module provides integration with BlazeSwap, a decentralized exchange on the Flare Network.
It handles token swaps and liquidity operations using BlazeSwap's smart contracts.
"""

import json
import time
from typing import Any, cast

import structlog
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.contract import Contract
from web3.types import TxParams

# Contract ABIs
ROUTER_ABI = json.loads('''[
    {"inputs":[{"internalType":"address","name":"_factory","type":"address"},{"internalType":"address","name":"_WETH","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},
    {"inputs":[],"name":"WETH","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint256","name":"amountADesired","type":"uint256"},{"internalType":"uint256","name":"amountBDesired","type":"uint256"},{"internalType":"uint256","name":"amountAMin","type":"uint256"},{"internalType":"uint256","name":"amountBMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"addLiquidity","outputs":[{"internalType":"uint256","name":"amountA","type":"uint256"},{"internalType":"uint256","name":"amountB","type":"uint256"},{"internalType":"uint256","name":"liquidity","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"amountTokenDesired","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"addLiquidityETH","outputs":[{"internalType":"uint256","name":"amountToken","type":"uint256"},{"internalType":"uint256","name":"amountETH","type":"uint256"},{"internalType":"uint256","name":"liquidity","type":"uint256"}],"stateMutability":"payable","type":"function"},
    {"inputs":[],"name":"factory","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint256","name":"reserveIn","type":"uint256"},{"internalType":"uint256","name":"reserveOut","type":"uint256"}],"name":"getAmountIn","outputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"}],"stateMutability":"pure","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"reserveIn","type":"uint256"},{"internalType":"uint256","name":"reserveOut","type":"uint256"}],"name":"getAmountOut","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],"stateMutability":"pure","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsIn","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactETHForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForETH","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}
]''')

FACTORY_ABI = json.loads('''[
    {"inputs":[{"internalType":"address","name":"_feeToSetter","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},
    {"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"token0","type":"address"},{"indexed":true,"internalType":"address","name":"token1","type":"address"},{"indexed":false,"internalType":"address","name":"pair","type":"address"},{"indexed":false,"internalType":"uint256","name":"","type":"uint256"}],"name":"PairCreated","type":"event"},
    {"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"allPairs","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"allPairsLength","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],"name":"createPair","outputs":[{"internalType":"address","name":"pair","type":"address"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"feeTo","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"feeToSetter","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"_feeTo","type":"address"}],"name":"setFeeTo","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"_feeToSetter","type":"address"}],"name":"setFeeToSetter","outputs":[],"stateMutability":"nonpayable","type":"function"}
]''')

ERC20_ABI = json.loads('''[
    {"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
    {"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":false,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
    {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
    {"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}
]''')

# BlazeSwap contract addresses
BLAZESWAP_FACTORY_ADDRESS = "0xF0f5e4CdE15b22A423E995415f373FEDC1f8F431"
BLAZESWAP_ROUTER_ADDRESS = "0x8D29b61C41CF318d15d031BE2928F79630e068e6"

TOKEN_ADDRESSES = {
    "C2FLR": "0x0000000000000000000000000000000000000000",  # Native token
    "FLR": "0x0000000000000000000000000000000000000000",  # Native token
    "WFLR": "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d",
    "WC2FLR": "0xC67DCE33D7A8efA5FfEB961899C73fe01bCe9273",  # Wrapped Coston2Flare
    "testALGO": "0xEEA81AF8BC97e550d95a77d74A44B0Be55bE8F9f",  # Test ALGO
    "testBCH": "0x7F720688AC040Bf03Bc86aDeD8Ef4fdB3eA47f0f",  # Test BCH
    "testDGB": "0xc95A32Ef14050df4b60f437e230Fc94aFD0309E6",  # Test DGB
    "testFIL": "0xAA6184134059391693f85D74b53ab614e279fBc3",  # Test FIL
    "testUSD": "0x6623C0BB56aDb150dC9C6BdB8682521354c2BF73",  # Test USD
    "testXLM": "0xCf5B4553Ea9C20DebAb75EC0B735DF6315684285",  # Test XLM
}

logger = structlog.get_logger(__name__)


class BlazeDEXProvider:
    """
    Provides integration with BlazeSwap, a decentralized exchange on the Flare Network.
    
    Attributes:
        w3 (Web3): Web3 instance for blockchain interactions
        router_contract (Contract): BlazeSwap router contract instance
        factory_contract (Contract): BlazeSwap factory contract instance
        logger (BoundLogger): Structured logger for the provider
    """
    
    def __init__(self, w3: Web3) -> None:
        """
        Initialize the BlazeSwap Provider.
        
        Args:
            w3 (Web3): Web3 instance for blockchain interactions
        """
        self.w3 = w3
        self.router_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(BLAZESWAP_ROUTER_ADDRESS),
            abi=ROUTER_ABI
        )
        self.factory_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(BLAZESWAP_FACTORY_ADDRESS),
            abi=FACTORY_ABI
        )
        self.logger = logger.bind(router="blazedex_provider")
        
        # Get WFLR address from router
        self.wflr_address = self.router_contract.functions.WETH().call()
        
    def get_token_contract(self, token_address: str) -> Contract:
        """
        Get the ERC20 token contract instance.
        
        Args:
            token_address (str): The token contract address
            
        Returns:
            Contract: The token contract instance
        """
        token_address = self.w3.to_checksum_address(token_address)
        return self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
    
    def get_token_address(self, token_symbol: str) -> str:
        """
        Get the token address from its symbol.
        
        Args:
            token_symbol (str): The token symbol (e.g., "FLR", "WFLR")
            
        Returns:
            str: The token address
            
        Raises:
            ValueError: If the token symbol is not recognized
        """
        token_symbol = token_symbol.upper()
        if token_symbol in TOKEN_ADDRESSES:
            return TOKEN_ADDRESSES[token_symbol]
        raise ValueError(f"Unknown token symbol: {token_symbol}")
    
    def get_token_balance(self, token_symbol: str, address: ChecksumAddress) -> float:
        """
        Get the token balance for an address.
        
        Args:
            token_symbol (str): The token symbol
            address (ChecksumAddress): The address to check balance for
            
        Returns:
            float: The token balance in human-readable format
        """
        token_symbol = token_symbol.upper()
        
        if token_symbol == "FLR":
            balance_wei = self.w3.eth.get_balance(address)
            return self.w3.from_wei(balance_wei, "ether")
        
        token_address = self.get_token_address(token_symbol)
        token_contract = self.get_token_contract(token_address)
        
        balance_wei = token_contract.functions.balanceOf(address).call()
        decimals = token_contract.functions.decimals().call()
        
        return balance_wei / (10 ** decimals)
    
    def approve_token(self, token_symbol: str, amount: float, from_address: ChecksumAddress) -> TxParams:
        """
        Create a transaction to approve the router to spend tokens.
        
        Args:
            token_symbol (str): The token symbol
            amount (float): The amount to approve in human-readable format
            from_address (ChecksumAddress): The address approving the tokens
            
        Returns:
            TxParams: The transaction parameters
            
        Raises:
            ValueError: If the token symbol is not recognized or is the native token
        """
        token_symbol = token_symbol.upper()
        
        if token_symbol == "FLR":
            raise ValueError("Cannot approve native FLR token")
        
        token_address = self.get_token_address(token_symbol)
        token_contract = self.get_token_contract(token_address)
        
        decimals = token_contract.functions.decimals().call()
        amount_wei = int(amount * (10 ** decimals))
        
        # Create the transaction
        tx = token_contract.functions.approve(
            self.router_contract.address,
            amount_wei
        ).build_transaction({
            'from': from_address,
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(from_address),
        })
        
        self.logger.info(
            "approve_token",
            token=token_symbol,
            amount=amount,
            from_address=from_address,
            router=self.router_contract.address
        )
        
        return tx
    
    def get_swap_quote(self, from_token: str, to_token: str, amount: float) -> tuple[float, float]:
        """
        Get a quote for swapping tokens.
        
        Args:
            from_token (str): The token symbol to swap from
            to_token (str): The token symbol to swap to
            amount (float): The amount to swap in human-readable format
            
        Returns:
            tuple[float, float]: The expected output amount and the price impact
            
        Raises:
            ValueError: If the token symbols are not recognized
        """
        from_token = from_token.upper()
        to_token = to_token.upper()
        
        # Get token addresses
        from_address = self.get_token_address(from_token)
        to_address = self.get_token_address(to_token)
        
        # Handle native FLR token
        if from_token == "FLR":
            from_address = self.wflr_address
        if to_token == "FLR":
            to_address = self.wflr_address
            
        # Get token contracts
        from_contract = self.get_token_contract(from_address) if from_address != TOKEN_ADDRESSES["FLR"] else None
        to_contract = self.get_token_contract(to_address) if to_address != TOKEN_ADDRESSES["FLR"] else None
        
        # Get token decimals
        from_decimals = from_contract.functions.decimals().call() if from_contract else 18
        to_decimals = to_contract.functions.decimals().call() if to_contract else 18
        
        # Convert amount to wei
        amount_wei = int(amount * (10 ** from_decimals))
        
        # Get the swap path
        path = [from_address, to_address]
        
        try:
            # Get the expected output amount
            amounts_out = self.router_contract.functions.getAmountsOut(
                amount_wei,
                path
            ).call()
            
            # Convert output amount from wei
            output_amount = amounts_out[1] / (10 ** to_decimals)
            
            # Calculate price impact (simplified)
            price_impact = 0.0  # In a real implementation, this would be calculated
            
            self.logger.info(
                "get_swap_quote",
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                output_amount=output_amount,
                price_impact=price_impact
            )
            
            return output_amount, price_impact
            
        except Exception as e:
            self.logger.error(
                "get_swap_quote_error",
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                error=str(e)
            )
            raise ValueError(f"Failed to get swap quote: {str(e)}")
    
    def create_swap_tx(
        self, 
        from_token: str, 
        to_token: str, 
        amount: float, 
        from_address: ChecksumAddress,
        slippage: float = 0.5
    ) -> TxParams:
        """
        Create a transaction to swap tokens.
        
        Args:
            from_token (str): The token symbol to swap from
            to_token (str): The token symbol to swap to
            amount (float): The amount to swap in human-readable format
            from_address (ChecksumAddress): The address initiating the swap
            slippage (float, optional): The slippage tolerance in percentage. Defaults to 0.5.
            
        Returns:
            TxParams: The transaction parameters
            
        Raises:
            ValueError: If the token symbols are not recognized
        """
        from_token = from_token.upper()
        to_token = to_token.upper()
        
        # Get token addresses
        from_address_token = self.get_token_address(from_token)
        to_address_token = self.get_token_address(to_token)
        
        # Handle native FLR token
        is_from_native = from_token == "FLR"
        is_to_native = to_token == "FLR"
        
        if is_from_native:
            from_address_token = self.wflr_address
        if is_to_native:
            to_address_token = self.wflr_address
            
        # Get token contracts
        from_contract = self.get_token_contract(from_address_token) if not is_from_native else None
        
        # Get token decimals
        from_decimals = from_contract.functions.decimals().call() if from_contract else 18
        
        # Convert amount to wei
        amount_wei = int(amount * (10 ** from_decimals))
        
        # Get the swap path
        path = [from_address_token, to_address_token]
        
        # Get the expected output amount
        amounts_out = self.router_contract.functions.getAmountsOut(
            amount_wei,
            path
        ).call()
        
        # Apply slippage to the output amount
        min_output_amount = int(amounts_out[1] * (1 - slippage / 100))
        
        # Set deadline to 20 minutes from now
        deadline = int(time.time()) + 1200
        
        # Create the transaction based on token types
        if is_from_native:
            # Swapping FLR to Token
            tx = self.router_contract.functions.swapExactETHForTokens(
                min_output_amount,
                path,
                from_address,
                deadline
            ).build_transaction({
                'from': from_address,
                'value': amount_wei,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(from_address),
            })
        elif is_to_native:
            # Swapping Token to FLR
            tx = self.router_contract.functions.swapExactTokensForETH(
                amount_wei,
                min_output_amount,
                path,
                from_address,
                deadline
            ).build_transaction({
                'from': from_address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(from_address),
            })
        else:
            # Swapping Token to Token
            tx = self.router_contract.functions.swapExactTokensForTokens(
                amount_wei,
                min_output_amount,
                path,
                from_address,
                deadline
            ).build_transaction({
                'from': from_address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(from_address),
            })
        
        self.logger.info(
            "create_swap_tx",
            from_token=from_token,
            to_token=to_token,
            input_amount=amount,
            min_output_amount=min_output_amount,
            from_address=from_address,
            slippage=slippage
        )
        
        return tx 