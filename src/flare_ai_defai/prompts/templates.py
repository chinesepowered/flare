from typing import Final

SEMANTIC_ROUTER: Final = """
Classify the user's message into one of the following categories:

1. GENERATE_ACCOUNT: User wants to create a new wallet or account
   Examples:
   - "Create a wallet for me"
   - "I need a new account"
   - "Generate a wallet"

2. SEND_TOKEN: User wants to send tokens to an address
   Examples:
   - "Send 5 FLR to 0x123..."
   - "Transfer 10 tokens to this address"
   - "I want to send some FLR"

3. TOKEN_SWAP: User wants to swap one token for another
   Examples:
   - "Swap 10 FLR for USDC"
   - "Exchange my FLR for USDT"
   - "Trade 5 WFLR to SFLR"
   - "Convert 100 FLR to WETH"

4. PRICE_QUOTE: User wants to check the price or rate for a token swap
   Examples:
   - "What's the price of FLR in USDC?"
   - "How much WETH can I get for 10 FLR?"
   - "Check the rate between FLR and USDT"
   - "What's the exchange rate for FLR to WETH?"

5. REQUEST_ATTESTATION: User is asking about remote attestation
   Examples:
   - "Show me your attestation"
   - "Prove your identity"
   - "Can I see your remote attestation?"

6. CONVERSATION: General conversation or questions
   Examples:
   - "What can you do?"
   - "Tell me about Flare Network"
   - "How does this work?"

Input: ${user_input}

Output EXACTLY one of: GENERATE_ACCOUNT, SEND_TOKEN, TOKEN_SWAP, PRICE_QUOTE, REQUEST_ATTESTATION, CONVERSATION
"""

GENERATE_ACCOUNT: Final = """
Generate a welcoming message that includes ALL of these elements in order:

1. Welcome message that conveys enthusiasm for the user joining
2. Security explanation:
   - Account is secured in a Trusted Execution Environment (TEE)
   - Private keys never leave the secure enclave
   - Hardware-level protection against tampering
3. Account address display:
   - EXACTLY as provided, make no changes: ${address}
   - Format with clear visual separation
4. Funding account instructions:
   - Tell the user to fund the new account: [Add funds to account](https://faucet.flare.network/coston2)

Important rules:
- DO NOT modify the address in any way
- Explain that addresses are public information
- Use markdown for formatting
- Keep the message concise (max 4 sentences)
- Avoid technical jargon unless explaining TEE

Example tone:
"Welcome to Flare! 🎉 Your new account is secured by secure hardware (TEE),
keeping your private keys safe and secure, you freely share your
public address: 0x123...
[Add funds to account](https://faucet.flare.network/coston2)
Ready to start exploring the Flare network?"
"""

TOKEN_SEND: Final = """
Extract EXACTLY two pieces of information from the input text for a token send operation:

1. DESTINATION ADDRESS
   Required format:
   • Must start with "0x"
   • Exactly 42 characters long
   • Hexadecimal characters only (0-9, a-f, A-F)
   • Extract COMPLETE address only
   • DO NOT modify or truncate
   • FAIL if no valid address found

2. TOKEN AMOUNT
   Number extraction rules:
   • Convert written numbers to digits (e.g., "five" → 5)
   • Handle decimals and integers
   • Convert ALL integers to float (e.g., 100 → 100.0)
   • Recognize common amount formats:
     - Decimal: "1.5", "0.5"
     - Integer: "1", "100"
     - With words: "5 tokens", "10 FLR"
   • Extract first valid number only
   • FAIL if no valid amount found

Input: ${user_input}

Rules:
- Both fields MUST be present
- Amount MUST be positive
- Amount MUST be float type
- DO NOT infer missing values
- DO NOT modify the address
- FAIL if either value is missing or invalid
"""

TOKEN_SWAP: Final = """
Extract EXACTLY three pieces of information from the input for a token swap operation:

1. SOURCE TOKEN (from_token)
   Valid formats:
   • Native token: "FLR" or "flr"
   • Listed pairs only: "USDC", "WFLR", "USDT", "sFLR", "WETH"
   • Case-insensitive match
   • Strip spaces and normalize to uppercase
   • FAIL if token not recognized

2. DESTINATION TOKEN (to_token)
   Valid formats:
   • Same rules as source token
   • Must be different from source token
   • FAIL if same as source token
   • FAIL if token not recognized

3. SWAP AMOUNT
   Number extraction rules:
   • Convert written numbers to digits (e.g., "five" → 5.0)
   • Handle decimal and integer inputs
   • Convert ALL integers to float (e.g., 100 → 100.0)
   • Valid formats:
     - Decimal: "1.5", "0.5"
     - Integer: "1", "100"
     - With tokens: "5 FLR", "10 USDC"
   • Extract first valid number only
   • Amount MUST be positive
   • FAIL if no valid amount found

Input: ${user_input}

Response format:
{
  "from_token": "<UPPERCASE_TOKEN_SYMBOL>",
  "to_token": "<UPPERCASE_TOKEN_SYMBOL>",
  "amount": <float_value>
}

Processing rules:
- All three fields MUST be present
- DO NOT infer missing values
- DO NOT allow same token pairs
- Normalize token symbols to uppercase
- Amount MUST be float type
- Amount MUST be positive
- FAIL if any value missing or invalid

Examples:
✓ "swap 100 FLR to USDC" → {"from_token": "FLR", "to_token": "USDC", "amount": 100.0}
✓ "exchange 50.5 flr for usdc" → {"from_token": "FLR", "to_token": "USDC", "amount": 50.5}
✗ "swap flr to flr" → FAIL (same token)
✗ "swap tokens" → FAIL (missing amount)
"""

CONVERSATIONAL: Final = """
I am Artemis, an AI assistant representing Flare, the blockchain network specialized in cross-chain data oracle services.

Key aspects I embody:
- Deep knowledge of Flare's technical capabilities in providing decentralized data to smart contracts
- Understanding of Flare's enshrined data protocols like Flare Time Series Oracle (FTSO) and  Flare Data Connector (FDC)
- Friendly and engaging personality while maintaining technical accuracy
- Creative yet precise responses grounded in Flare's actual capabilities

When responding to queries, I will:
1. Address the specific question or topic raised
2. Provide technically accurate information about Flare when relevant
3. Maintain conversational engagement while ensuring factual correctness
4. Acknowledge any limitations in my knowledge when appropriate

<input>
${user_input}
</input>
"""

REMOTE_ATTESTATION: Final = """
A user wants to perform a remote attestation with the TEE, make the following process clear to the user:

1. Requirements for the users attestation request:
   - The user must provide a single random message
   - Message length must be between 10-74 characters
   - Message can include letters and numbers
   - No additional text or instructions should be included

2. Format requirements:
   - The user must send ONLY the random message in their next response

3. Verification process:
   - After receiving the attestation response, the user should https://jwt.io
   - They should paste the complete attestation response into the JWT decoder
   - They should verify that the decoded payload contains your exact random message
   - They should confirm the TEE signature is valid
   - They should check that all claims in the attestation response are present and valid
"""


TX_CONFIRMATION: Final = """
Respond with a confirmation message for the successful transaction that:

1. Required elements:
   - Express positive acknowledgement of the successful transaction
   - Include the EXACT transaction hash link with NO modifications:
     [See transaction on Explorer](${block_explorer}/tx/${tx_hash})
   - Place the link on its own line for visibility

2. Message structure:
   - Start with a clear success confirmation
   - Include transaction link in unmodified format
   - End with a brief positive closing statement

3. Link requirements:
   - Preserve all variables: ${block_explorer} and ${tx_hash}
   - Maintain exact markdown link syntax
   - Keep URL structure intact
   - No additional formatting or modification of the link

Sample format:
Great news! Your transaction has been successfully confirmed. 🎉

[See transaction on Explorer](${block_explorer}/tx/${tx_hash})

Your transaction is now securely recorded on the blockchain.
"""

FOLLOW_UP_TOKEN_SWAP: Final = """
I need a bit more information to process your swap request. Please specify:

1. The token you want to swap FROM (e.g., FLR, USDC, WFLR)
2. The token you want to swap TO (e.g., USDC, WFLR, SFLR)
3. The amount you want to swap

For example:
- "Swap 10 FLR to USDC"
- "Exchange 5 USDC for WFLR"
- "Trade 100 FLR for SFLR"

Currently supported tokens: FLR, WFLR, USDC, USDT, WETH, SFLR
"""

price_quote: Final = """
Extract EXACTLY two pieces of information from the input for a token price quote:

1. SOURCE TOKEN (from_token)
   Valid formats:
   • Native token: "FLR" or "flr"
   • Listed pairs only: "USDC", "WFLR", "USDT", "sFLR", "WETH"
   • Case-insensitive match
   • Strip spaces and normalize to uppercase
   • FAIL if token not recognized

2. DESTINATION TOKEN (to_token)
   Valid formats:
   • Same rules as source token
   • Must be different from source token
   • FAIL if same as source token
   • FAIL if token not recognized

Input: ${user_input}

Response format:
{
  "from_token": "<UPPERCASE_TOKEN_SYMBOL>",
  "to_token": "<UPPERCASE_TOKEN_SYMBOL>"
}

Processing rules:
- Both fields MUST be present
- DO NOT infer missing values
- DO NOT allow same token pairs
- Normalize token symbols to uppercase
- FAIL if any value missing or invalid

Examples:
✓ "What's the price of FLR in USDC?" → {"from_token": "FLR", "to_token": "USDC"}
✓ "How much WETH can I get for 10 FLR?" → {"from_token": "FLR", "to_token": "WETH"}
✓ "Check the rate between FLR and USDT" → {"from_token": "FLR", "to_token": "USDT"}
✗ "What's the price of FLR?" → FAIL (missing to_token)
✗ "What's the exchange rate for FLR to FLR?" → FAIL (same token)
"""
