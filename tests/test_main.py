import asyncio
from collections import deque
import aiofiles
import aiohttp
from typing import List
from src.main import ProxyManager, validate_input_files, validate_output
from src.exceptions import NoAvailableProxiesError, UnexpectedResponseCode
import pytest

MAX_CONCURRENT_REQUESTS_PER_PROXY = 30
MAX_RETRY_ATTEMPTS = 10


class MockProxy:
    def __init__(self, address: str, response_sequence: List[int] = None) -> None:
        self.address = address
        self.active = True
        self.retry_count = 0
        self.response_sequence = response_sequence or [
            200
        ]  # Default to 200 OK if no sequence provided
        self.response_index = 0

    @property
    def is_active(self) -> bool:
        return self.active

    def block_proxy(self) -> None:
        self.active = False

    async def fetch_single(
        self,
        session: aiohttp.ClientSession,
        input_string: str,
        output_file: str,
        attempted_requests: set,
    ) -> bool:
        # Simulate fetch_single behavior without actual HTTP request
        if input_string in attempted_requests:
            return False  # Skip if already attempted

        attempted_requests.add(input_string)

        # Determine response code from the sequence
        response_code = self.response_sequence[self.response_index]
        self.response_index = (self.response_index + 1) % len(self.response_sequence)

        if response_code == 200:
            # Simulate response handling for 200 OK
            data = {"information": "mock_data"}
            async with aiofiles.open(output_file, "a") as f:
                await f.write(f"{input_string} {data['information']}\n")

            self.retry_count = 0  # Reset retry count on success
            return True
        elif response_code == 503:
            # Simulate response handling for 503 Service Unavailable
            self.retry_count += 1
            if self.retry_count >= MAX_RETRY_ATTEMPTS:
                self.block_proxy()

            return False
        else:
            raise UnexpectedResponseCode(f"Unexpected response code: {response_code}")


@pytest.mark.asyncio
async def test_regular_request_through_proxy(tmp_path):
    mock_input_strings = deque(["test_input" * 30])
    output_file = tmp_path / "output.txt"
    input_file = tmp_path / "input.txt"
    input_file.write_text("\n".join(mock_input_strings))

    proxy_addresses = ["http://mock.proxy1"]
    proxies = [MockProxy(address, [200]) for address in proxy_addresses]
    manager = ProxyManager(proxy_addresses)
    manager.proxies = {proxy.address: proxy for proxy in proxies}

    async with aiohttp.ClientSession() as session:
        await manager.distribute_requests(session, mock_input_strings, str(output_file))

    validate_output(input_file=str(input_file), output_file=str(output_file))


@pytest.mark.asyncio
async def test_blocking_mechanism_multiple_proxies(tmp_path):
    mock_input_strings = deque(["test_input" * 30])
    output_file = tmp_path / "output.txt"
    input_file = tmp_path / "input.txt"
    input_file.write_text("\n".join(mock_input_strings))

    manager = ProxyManager(["http://mock.proxy1", "http://mock.proxy2"])
    manager.proxies = {
        "http://mock.proxy1": MockProxy("http://mock.proxy1", [503]),
        "http://mock.proxy2": MockProxy("http://mock.proxy2", [200]),
    }
    manager.proxies["http://mock.proxy1"].block_proxy()

    async with aiohttp.ClientSession() as session:
        await manager.distribute_requests(session, mock_input_strings, str(output_file))

    validate_output(input_file=str(input_file), output_file=str(output_file))


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    raises=UnexpectedResponseCode,
    reason="Program has encountered a code other than 200 or 503",
)
async def test_request_fails_after_success_with_unexpected_code(tmp_path):
    mock_input_strings = deque(["test_input1", "test_input2", "test_input3"])
    output_file = tmp_path / "output.txt"
    input_file = tmp_path / "input.txt"
    input_file.write_text("\n".join(mock_input_strings))

    # Mock ProxyManager with mock proxies
    proxy_addresses = ["http://mock.proxy1"]
    proxies = [MockProxy(address, [200, 400, 200]) for address in proxy_addresses]
    manager = ProxyManager(proxy_addresses)
    manager.proxies = {proxy.address: proxy for proxy in proxies}
    async with aiohttp.ClientSession() as session:
        await manager.distribute_requests(session, mock_input_strings, str(output_file))


@pytest.mark.asyncio
async def test_general_read_write_from_files(tmp_path):
    mock_input_strings = deque(["test_input1", "test_input2", "test_input3"])
    output_file = tmp_path / "output.txt"
    input_file = tmp_path / "input.txt"
    input_file.write_text("\n".join(mock_input_strings))

    # Mock ProxyManager with mock proxies
    proxy_addresses = ["http://mock.proxy1"]
    proxies = [MockProxy(address, [200, 200, 200]) for address in proxy_addresses]
    manager = ProxyManager(proxy_addresses)
    manager.proxies = {proxy.address: proxy for proxy in proxies}

    async with aiohttp.ClientSession() as session:
        await manager.distribute_requests(session, mock_input_strings, str(output_file))

    validate_output(input_file=str(input_file), output_file=str(output_file))


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True, raises=NoAvailableProxiesError, reason="No active proxies"
)
async def test_no_active_proxies(tmp_path):
    # Setup
    mock_input_strings = deque(["test_input\n"] * 1)  # Only one request
    output_file = tmp_path / "output.txt"
    input_file = tmp_path / "input.txt"
    input_file.write_text("\n".join(mock_input_strings))

    proxy_addresses = ["http://mock.proxy1"]
    manager = ProxyManager(proxy_addresses)
    manager.proxies = {
        address: MockProxy(address, [200]) for address in proxy_addresses
    }
    manager.proxies["http://mock.proxy1"].block_proxy()  # Block the only proxy
    async with aiohttp.ClientSession() as session:
        await manager.distribute_requests(session, mock_input_strings, str(output_file))


@pytest.mark.asyncio
async def test_validate_input_files(tmp_path):
    # Setup
    input_file = tmp_path / "input.txt"
    addresses_file = tmp_path / "addresses.txt"

    input_file.write_text("Test input")
    addresses_file.write_text("http://mock.proxy1")

    # Test
    validate_input_files(str(input_file), str(addresses_file))


@pytest.mark.asyncio
async def test_empty_input_file(tmp_path):
    # Setup
    mock_input_strings = deque([])
    output_file = tmp_path / "output.txt"
    input_file = tmp_path / "input.txt"
    input_file.write_text("")  # Empty input file

    proxy_addresses = ["http://mock.proxy1"]
    proxies = [MockProxy(address, [200]) for address in proxy_addresses]
    manager = ProxyManager(proxy_addresses)
    manager.proxies = {proxy.address: proxy for proxy in proxies}

    # Test
    async with aiohttp.ClientSession() as session:
        await manager.distribute_requests(session, mock_input_strings, str(output_file))

    # Validation
    assert not output_file.exists(), "Output file should not be created for empty input"
