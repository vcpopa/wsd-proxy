import sys
import os
import logging
from typing import List
from collections import deque
import asyncio
import aiohttp
import aiofiles
from src.exceptions import NoAvailableProxiesError, UnexpectedResponseCode


MAX_CONCURRENT_REQUESTS_PER_PROXY = 30
MAX_RETRY_ATTEMPTS = 10

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class Proxy:
    """
    Represents a proxy server that can make HTTP requests.

    Attributes:
        address (str): The address of the proxy server.
        semaphore (asyncio.Semaphore): Semaphore for limiting concurrent requests.
        active (bool): Flag indicating if the proxy is active.
        retry_count (int): Number of times retries have been attempted for the proxy.
    """
    def __init__(self, address: str, semaphore: asyncio.Semaphore) -> None:
        """
        Initialize the Proxy instance.

        Args:
            address (str): The address of the proxy server.
            semaphore (asyncio.Semaphore): Semaphore for limiting concurrent requests.
        """
        self.address = address
        self.active = True
        self.semaphore = semaphore
        self.retry_count = 0

    @property
    def is_active(self) -> bool:
        """
        Check if the proxy is currently active.

        Returns:
            bool: True if the proxy is active, False otherwise.
        """
        return self.active

    def block_proxy(self) -> None:
        """
        Block the proxy server, marking it as inactive.

        Logs a critical message indicating the proxy has been blocked.
        """
        self.active = False
        logging.critical(f"Proxy {self.address} has been blocked.")

    async def fetch_single(
        self,
        session: aiohttp.ClientSession,
        input_string: str,
        output_file: str,
        attempted_requests: set,
    ) -> bool:
        """
        Fetch data from the proxy server for a single request.

        Args:
            session (aiohttp.ClientSession): Client session for making HTTP requests.
            input_string (str): Input data for the request.
            output_file (str): File path to write the fetched data.
            attempted_requests (set): Set of attempted input strings.

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        url = f"{self.address}/api/data?input={input_string}"
        try:
            if input_string in attempted_requests:
                return False  # Skip if already attempted

            attempted_requests.add(input_string)

            async with self.semaphore:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        async with aiofiles.open(output_file, "a") as f:
                            await f.write(f"{input_string} {data['information']}\n")
                        logging.info(
                            f"Received data for {input_string} from {self.address}"
                        )
                        self.retry_count = 0  # Reset retry count on success
                        return True
                    elif response.status == 503:
                        self.retry_count += 1
                        if self.retry_count >= MAX_RETRY_ATTEMPTS:
                            self.block_proxy()
                        logging.warning(
                            f"Received 503 error for {input_string} from {self.address}. Retry count: {self.retry_count}"
                        )
                        return False
                    else:
                        raise UnexpectedResponseCode(
                            f"Unexpected response code: {response.status}"
                        )
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching data from {self.address}: {str(e)}")
            raise e


class ProxyManager:
    """
    Manages multiple proxy servers and distributes requests across them.

    Attributes:
        proxy_addresses (List[str]): List of proxy server addresses.
        proxies (dict): Dictionary mapping proxy addresses to Proxy objects.
        semaphore (asyncio.Semaphore): Semaphore for limiting concurrent requests.
    """
    def __init__(self, proxy_addresses: List[str]) -> None:
        """
        Initialize the ProxyManager instance.

        Args:
            proxy_addresses (List[str]): List of proxy server addresses.
        """
        self.proxies = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS_PER_PROXY)
        for address in proxy_addresses:
            self.proxies[address] = Proxy(address, self.semaphore)

    @property
    def active_proxies(self) -> List[Proxy]:
        """
        Get a list of currently active proxy objects.

        Returns:
            List[Proxy]: List of active Proxy objects.
        """
        return [proxy for proxy in self.proxies.values() if proxy.is_active]

    async def distribute_requests(
        self, session: aiohttp.ClientSession, input_strings: deque, output_file: str
    ) -> None:
        """
        Distribute requests across active proxies.

        Args:
            session (aiohttp.ClientSession): Client session for making HTTP requests.
            input_strings (deque): Queue of input strings to process.
            output_file (str): File path to write the fetched data.
        """
        attempted_requests = set()

        while input_strings:
            active_proxies = self.active_proxies[:]
            if not active_proxies:
                raise NoAvailableProxiesError("No active proxies available.")

            tasks = []

            for proxy in active_proxies:
                chunk = list(input_strings)[:MAX_CONCURRENT_REQUESTS_PER_PROXY]
                input_strings = deque(
                    list(input_strings)[MAX_CONCURRENT_REQUESTS_PER_PROXY:]
                )

                for input_string in chunk:
                    tasks.append(
                        asyncio.create_task(
                            proxy.fetch_single(
                                session, input_string, output_file, attempted_requests
                            )
                        )
                    )

            # Execute tasks concurrently across all proxies
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for task, input_string in zip(tasks, chunk):
                if isinstance(task, asyncio.Task) and task.done():
                    task_result = task.result()

                    if task_result is False:
                        input_strings.appendleft(input_string)

    async def collect_information(self, input_file: str, output_file: str) -> None:
        """
        Collect information from input file using active proxies.

        Args:
            input_file (str): Path to the input file containing data to fetch.
            output_file (str): File path to write the fetched data.
        """
        async with aiohttp.ClientSession() as session:
            async with aiofiles.open(input_file, "r") as f:
                input_strings = deque(
                    line.strip() for line in await f.readlines() if line.strip()
                )

            await self.distribute_requests(session, input_strings, output_file)


def validate_input_files(*files: str) -> None:
    """
    Check if all the specified files exist.
    If any file does not exist, raise an error.

    :param files: Paths to the files to check
    :raises FileNotFoundError: If any of the files do not exist
    """
    for file in files:
        if not os.path.exists(file):
            logging.error(f"Missing input {file}")
            raise FileNotFoundError(f"Error: {file} does not exist.")


def validate_output(input_file: str, output_file: str) -> None:
    """
    Check if the lengths of the input and output files are equal.
    If not, raise an error.

    :param input_file: Path to the input file
    :param output_file: Path to the output file
    """
    with open(input_file, "r") as infile, open(output_file, "r") as outfile:
        input_lines = infile.readlines()
        output_lines = outfile.readlines()

    if len(input_lines) != len(output_lines):
        logging.error(
            f"The lengths of the input file ({len(input_lines)}) and output file ({len(output_lines)})are not equal."
        )
    else:
        logging.info("Process completed successfully with no loss of data")


async def main(input_file: str, addresses_file: str, output_file: str) -> None:
    """
    Main function to orchestrate data collection using proxies.

    Args:
        input_file (str): Path to the input file containing data to fetch.
        addresses_file (str): Path to the file containing proxy addresses.
        output_file (str): File path to write the fetched data.
    """
    async with aiofiles.open(addresses_file, "r") as f:
        proxy_addresses = [line.strip() for line in await f.readlines() if line.strip()]
    validate_input_files(input_file, addresses_file)
    proxy_manager = ProxyManager(proxy_addresses)
    await proxy_manager.collect_information(input_file, output_file)
    validate_output(input_file=input_file, output_file=output_file)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python main.py input addresses output")
        sys.exit(1)

    input_file = sys.argv[1]
    addresses_file = sys.argv[2]
    output_file = sys.argv[3]

    asyncio.run(main(input_file, addresses_file, output_file))
