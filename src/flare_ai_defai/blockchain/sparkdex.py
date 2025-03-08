"""
SparkDEX Integration Module

This module provides integration with SparkDEX, a decentralized exchange on the Flare Network.
It handles token swaps and liquidity operations using SparkDEX's smart contracts.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

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
    {"inputs":[{"internalType":"uint256","name":"amountA","type":"uint256"},{"internalType":"uint256","name":"reserveA","type":"uint256"},{"internalType":"uint256","name":"reserveB","type":"uint256"}],"name":"quote","outputs":[{"internalType":"uint256","name":"amountB","type":"uint256"}],"stateMutability":"pure","type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountAMin","type":"uint256"},{"internalType":"uint256","name":"amountBMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"removeLiquidity","outputs":[{"internalType":"uint256","name":"amountA","type":"uint256"},{"internalType":"uint256","name":"amountB","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"removeLiquidityETH","outputs":[{"internalType":"uint256","name":"amountToken","type":"uint256"},{"internalType":"uint256","name":"amountETH","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"removeLiquidityETHSupportingFeeOnTransferTokens","outputs":[{"internalType":"uint256","name":"amountETH","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"bool","name":"approveMax","type":"bool"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"removeLiquidityETHWithPermit","outputs":[{"internalType":"uint256","name":"amountToken","type":"uint256"},{"internalType":"uint256","name":"amountETH","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"bool","name":"approveMax","type":"bool"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"removeLiquidityETHWithPermitSupportingFeeOnTransferTokens","outputs":[{"internalType":"uint256","name":"amountETH","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountAMin","type":"uint256"},{"internalType":"uint256","name":"amountBMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"bool","name":"approveMax","type":"bool"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"removeLiquidityWithPermit","outputs":[{"internalType":"uint256","name":"amountA","type":"uint256"},{"internalType":"uint256","name":"amountB","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapETHForExactTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactETHForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactETHForTokensSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForETH","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForETHSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokensSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint256","name":"amountInMax","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapTokensForExactETH","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint256","name":"amountInMax","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapTokensForExactTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},
    {"stateMutability":"payable","type":"receive"}
]''')

ERC20_ABI = json.loads('''[
    {"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
    {"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":false,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
    {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
    {"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
    {"payable":true,"stateMutability":"payable","type":"fallback"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"owner","type":"address"},{"indexed":true,"name":"spender","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Approval","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}
]''')

# Contract addresses
ROUTER_ADDRESS = "0x4a1E5A90e9943467FAd1acea1E7F0e5e88472a1e"  # UniswapV2Router02
FACTORY_ADDRESS = "0x16b619B04c961E8f4F06C10B42FDAbb328980A89"  # V2Factory
WFLR_ADDRESS = "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d"  # Wrapped FLR

# Token addresses - these would typically be loaded from a configuration
TOKEN_ADDRESSES = {
    "FLR": "0x0000000000000000000000000000000000000000",  # Native token
    "WFLR": "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d",
    "USDC": "0xcD75D6d2Ea389BFE55ECf8Ee9B83dDc5E5513C1d",
    "USDT": "0x9Bf3C5E5c9F78a3DBf33d216d5Bc5EEa3e095BF5",
    "WETH": "0x5D3c0F4cA5EE99f8E8F59Ff9A5fAb04F6a7e007f",
    "SFLR": "0x02f0826ef6aD107Cfc861152B32B52fD11BaB9ED",
}

logger = structlog.get_logger(__name__)


class SparkDEXProvider:
    """
    Provider for interacting with SparkDEX on the Flare Network.
    
    This class provides methods for token swaps and other DEX operations
    using SparkDEX's smart contracts.
    """
    
    def __init__(self, w3: Web3) -> None:
        """
        Initialize the SparkDEX provider.
        
        Args:
            w3 (Web3): Web3 instance for blockchain interactions
        """
        self.w3 = w3
        self.router = self.w3.eth.contract(
            address=self.w3.to_checksum_address(ROUTER_ADDRESS),
            abi=ROUTER_ABI
        )
        self.logger = logger.bind(provider="sparkdex")
        
    def get_token_contract(self, token_address: str) -> Contract:
        """
        Get a contract instance for an ERC20 token.
        
        Args:
            token_address (str): Address of the token contract
            
        Returns:
            Contract: Web3 contract instance for the token
        """
        return self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
    
    def get_token_address(self, token_symbol: str) -> str:
        """
        Get the address for a token by its symbol.
        
        Args:
            token_symbol (str): Token symbol (e.g., "FLR", "USDC")
            
        Returns:
            str: Token address
            
        Raises:
            ValueError: If token symbol is not recognized
        """
        token_symbol = token_symbol.upper()
        if token_symbol not in TOKEN_ADDRESSES:
            msg = f"Unsupported token: {token_symbol}"
            raise ValueError(msg)
        return TOKEN_ADDRESSES[token_symbol]
    
    def get_token_balance(self, token_symbol: str, address: ChecksumAddress) -> float:
        """
        Get the balance of a token for an address.
        
        Args:
            token_symbol (str): Token symbol
            address (ChecksumAddress): Address to check balance for
            
        Returns:
            float: Token balance in human-readable format
        """
        token_symbol = token_symbol.upper()
        
        # Handle native FLR differently
        if token_symbol == "FLR":
            balance_wei = self.w3.eth.get_balance(address)
            return float(self.w3.from_wei(balance_wei, "ether"))
        
        # For ERC20 tokens
        token_address = self.get_token_address(token_symbol)
        token_contract = self.get_token_contract(token_address)
        balance = token_contract.functions.balanceOf(address).call()
        decimals = token_contract.functions.decimals().call()
        
        # Convert to human-readable format
        return float(balance) / (10 ** decimals)
    
    def approve_token(self, token_symbol: str, amount: float, from_address: ChecksumAddress) -> TxParams:
        """
        Create a transaction to approve the router to spend tokens.
        
        Args:
            token_symbol (str): Token symbol
            amount (float): Amount to approve
            from_address (ChecksumAddress): Address approving the tokens
            
        Returns:
            TxParams: Transaction parameters for the approval
            
        Raises:
            ValueError: If token is not supported or is the native token
        """
        token_symbol = token_symbol.upper()
        
        # Native FLR doesn't need approval
        if token_symbol == "FLR":
            msg = "Native FLR doesn't need approval"
            raise ValueError(msg)
        
        token_address = self.get_token_address(token_symbol)
        token_contract = self.get_token_contract(token_address)
        
        # Get token decimals
        decimals = token_contract.functions.decimals().call()
        
        # Convert amount to token units
        amount_in_token_units = int(amount * (10 ** decimals))
        
        # Create approval transaction
        tx = token_contract.functions.approve(
            ROUTER_ADDRESS,
            amount_in_token_units
        ).build_transaction({
            "from": from_address,
            "nonce": self.w3.eth.get_transaction_count(from_address),
            "gas": 100000,  # Estimated gas for approval
            "maxFeePerGas": self.w3.eth.gas_price,
            "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
            "chainId": self.w3.eth.chain_id,
            "type": 2,  # EIP-1559 transaction
        })
        
        return tx
    
    def get_swap_quote(self, from_token: str, to_token: str, amount: float) -> Tuple[float, float]:
        """
        Get a quote for swapping tokens.
        
        Args:
            from_token (str): Symbol of token to swap from
            to_token (str): Symbol of token to swap to
            amount (float): Amount of from_token to swap
            
        Returns:
            Tuple[float, float]: (expected output amount, price impact percentage)
            
        Raises:
            ValueError: If tokens are not supported or if there's no liquidity
        """
        from_token = from_token.upper()
        to_token = to_token.upper()
        
        # Get token addresses
        from_address = self.get_token_address(from_token)
        to_address = self.get_token_address(to_token)
        
        # Handle native FLR
        if from_token == "FLR":
            from_address = WFLR_ADDRESS
        if to_token == "FLR":
            to_address = WFLR_ADDRESS
        
        # Create path for the swap
        path = [from_address, to_address]
        
        # Get decimals for from_token
        if from_token == "FLR":
            decimals = 18  # FLR has 18 decimals
        else:
            from_token_contract = self.get_token_contract(from_address)
            decimals = from_token_contract.functions.decimals().call()
        
        # Convert amount to token units
        amount_in_token_units = int(amount * (10 ** decimals))
        
        try:
            # Get amounts out
            amounts_out = self.router.functions.getAmountsOut(
                amount_in_token_units,
                path
            ).call()
            
            # Get decimals for to_token
            if to_token == "FLR":
                to_decimals = 18
            else:
                to_token_contract = self.get_token_contract(to_address)
                to_decimals = to_token_contract.functions.decimals().call()
            
            # Convert output amount to human-readable format
            output_amount = float(amounts_out[1]) / (10 ** to_decimals)
            
            # Calculate price impact (simplified)
            # In a real implementation, you would compare to the current market price
            price_impact = 0.5  # Placeholder for a more complex calculation
            
            return output_amount, price_impact
            
        except Exception as e:
            self.logger.error("swap_quote_failed", error=str(e))
            msg = f"Failed to get swap quote: {str(e)}"
            raise ValueError(msg) from e
    
    def create_swap_tx(
        self, 
        from_token: str, 
        to_token: str, 
        amount: float, 
        from_address: ChecksumAddress,
        slippage: float = 0.5
    ) -> TxParams:
        """
        Create a transaction for swapping tokens.
        
        Args:
            from_token (str): Symbol of token to swap from
            to_token (str): Symbol of token to swap to
            amount (float): Amount of from_token to swap
            from_address (ChecksumAddress): Address initiating the swap
            slippage (float, optional): Slippage tolerance percentage. Defaults to 0.5.
            
        Returns:
            TxParams: Transaction parameters for the swap
            
        Raises:
            ValueError: If tokens are not supported or if there's no liquidity
        """
        from_token = from_token.upper()
        to_token = to_token.upper()
        
        # Get token addresses
        from_address_token = self.get_token_address(from_token)
        to_address_token = self.get_token_address(to_token)
        
        # Handle native FLR
        is_from_native = from_token == "FLR"
        is_to_native = to_token == "FLR"
        
        if is_from_native:
            from_address_token = WFLR_ADDRESS
        if is_to_native:
            to_address_token = WFLR_ADDRESS
        
        # Create path for the swap
        path = [from_address_token, to_address_token]
        
        # Get decimals for from_token
        if is_from_native:
            decimals = 18  # FLR has 18 decimals
        else:
            from_token_contract = self.get_token_contract(from_address_token)
            decimals = from_token_contract.functions.decimals().call()
        
        # Convert amount to token units
        amount_in_token_units = int(amount * (10 ** decimals))
        
        # Get expected output amount
        try:
            amounts_out = self.router.functions.getAmountsOut(
                amount_in_token_units,
                path
            ).call()
            
            # Apply slippage tolerance
            min_amount_out = int(amounts_out[1] * (1 - slippage / 100))
            
            # Set deadline to 20 minutes from now
            deadline = self.w3.eth.get_block('latest').timestamp + 1200
            
            # Create the appropriate swap transaction based on token types
            if is_from_native and not is_to_native:
                # Swapping FLR to Token
                tx = self.router.functions.swapExactETHForTokens(
                    min_amount_out,
                    path,
                    from_address,
                    deadline
                ).build_transaction({
                    "from": from_address,
                    "value": amount_in_token_units,
                    "nonce": self.w3.eth.get_transaction_count(from_address),
                    "gas": 200000,  # Estimated gas
                    "maxFeePerGas": self.w3.eth.gas_price,
                    "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
                    "chainId": self.w3.eth.chain_id,
                    "type": 2,  # EIP-1559 transaction
                })
            elif not is_from_native and is_to_native:
                # Swapping Token to FLR
                tx = self.router.functions.swapExactTokensForETH(
                    amount_in_token_units,
                    min_amount_out,
                    path,
                    from_address,
                    deadline
                ).build_transaction({
                    "from": from_address,
                    "nonce": self.w3.eth.get_transaction_count(from_address),
                    "gas": 200000,  # Estimated gas
                    "maxFeePerGas": self.w3.eth.gas_price,
                    "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
                    "chainId": self.w3.eth.chain_id,
                    "type": 2,  # EIP-1559 transaction
                })
            else:
                # Swapping Token to Token
                tx = self.router.functions.swapExactTokensForTokens(
                    amount_in_token_units,
                    min_amount_out,
                    path,
                    from_address,
                    deadline
                ).build_transaction({
                    "from": from_address,
                    "nonce": self.w3.eth.get_transaction_count(from_address),
                    "gas": 200000,  # Estimated gas
                    "maxFeePerGas": self.w3.eth.gas_price,
                    "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
                    "chainId": self.w3.eth.chain_id,
                    "type": 2,  # EIP-1559 transaction
                })
            
            return tx
            
        except Exception as e:
            self.logger.error("swap_tx_failed", error=str(e))
            msg = f"Failed to create swap transaction: {str(e)}"
            raise ValueError(msg) from e 