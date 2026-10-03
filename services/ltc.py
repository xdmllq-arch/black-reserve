import aiohttp


async def get_ltc_usd_price() -> float:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "litecoin",
        "vs_currencies": "usd",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=15) as response:
            response.raise_for_status()
            data = await response.json()

    return float(data["litecoin"]["usd"])


async def get_incoming_transactions(address: str):
    url = f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/full"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as response:
            response.raise_for_status()
            data = await response.json()

    return data.get("txs", [])
