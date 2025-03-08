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
BLAZESWAP_FACTORY_ADDRESS = "0x440602f459D7Dd500a74528003e6A20A46d6e2A6"
BLAZESWAP_ROUTER_ADDRESS = "0xe3A1b355ca63abCBC9589334B5e609583C7BAa06"

TOKEN_ADDRESSES = {
    "C2FLR": "0x0000000000000000000000000000000000000000",  # Native token
    "FLR": "0x0000000000000000000000000000000000000000",  # Native token
    "WFLR": "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d",  # Wrapped Flare
    "BNZ": "0xfD3449E8Ee31117a848D41Ee20F497a9bCb53164",  # Bonez
    "BUNNY": "0x1aa5282692398c078e71Fb3e4A85660d1BF8F586",  # BunnyToken
    "eUSDT": "0x96B41289D90444B8adD57e6F265DB5aE8651DF29",  # Enosys USDT
    "eETH": "0xa76DCDdcE60a442d69Bac7158F3660f50921b122",  # Enosys ETH
    "FINU": "0x282b88514A52FcAdCD92b742745398f3574697d4",  # Finu
    "FLX": "0x22757fb83836e3F9F0F353126cACD3B1Dc82a387",  # FlareFox
    "GEMIN": "0xb56718d45cffc7ca9d6b8b9e631f0657b971043f",  # Gemin Flare
    "GFLR": "0x90e157A979074f9f2fe8B124Ba08e6F72dc812FC",  # GFlare
    "JOULE": "0xE6505f92583103AF7ed9974DEC451A7Af4e3A3bE",  # Joule
    "PFL": "0xB5010D5Eb31AA8776b52C7394B76D6d627501C73",  # Pangolin Flare
    "PHIL": "0x932E691aA8c8306C4bB0b19F3f00a284371be8Ba",  # Phili Inu
    "POODLE": "0xC18f99CE6DD6278BE2D3f1e738Ed11623444aE33",  # PoodleCoin
    "sFLR": "0x12e605bc104e93B45e1aD99F9e555f659051c2BB",  # Staked FLR
    "USDC.e": "0xFbDa5F676cB37624f28265A144A48B0d6e87d3b6",  # Bridged USDC (Stargate)
    "USDT": "0x0B38e83B86d491735fEaa0a791F65c2B99535396",  # Bridged Tether USD (Stargate)
    "USDX": "0x4A771Cc1a39FDd8AA08B8EA51F7Fd412e73B3d2B",  # Hex Trust USD
    "FLR": "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d",  # Flare
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