# Concurrent requests

Your task is produce a CLI application meeting the specification below. I recommend spending no more that 4 hours in total on this task. You can use any programming language  + any build system + any external dependencies that you want.

## Problem statement

Given a set of strings S we need an application to collect information about every string in S from some publicly accessible 3rd party http endpoint. Your task is to implement this application which accepts input as command line arguments (more details about this later), makes http requests to collect the information and writes to some output file.

The app needs to be written in a way which maximises our total request throughput so we collect the information as quickly as possible. Unfortunately the 3rd party server tracks the source ip address of clients and **if any client address exceeds 30 concurrent requests then it is blocked**. Any further requests sent from a blocked address will always have a 503 response (however a 503 response is not sufficient to imply it has been blocked).

In order to increase our throughput beyond this limit we will distribute our requests across a set of our own proxies which each has a different address. With n proxies we can therefore have **30 * n** concurrent requests. The proxies are simple processes which forward the incoming request to the 3rd party server. For our purposes we can treat them as a black box with a single http endpoint, you do not need to worry about how they interact with the 3rd party endpoint. You may assume that connection to the proxies is reliable and response times are < 5 seconds.


The output must be written in such a way that if the app terminates unexpectedly for whatever reason we minimise the loss of information which we already collected. In practice this means the data should be written to the output file as soon as possible after it has been collected.

A Docker image for the proxy has been provided which help you to manually test your code. This same image will be used when we test your code works. There is a section at the bottom containing instructions for this image.

## Proxy endpoint

The http proxies have a single endpoint which your client code will need to use. It looks like

```curl
GET /api/data?input=<s>
```

The query parameter corresponds to the input string we need to fetch information for. The response has multiple possible codes, your application should handle them in the following way:

| Code | Expected application behaviour |
|:-------------|:--------------|
| 200 | Store the result and continue the collection   |
| 503 | Continue the collection, ensuring the failed request is retried so the info is not missed   |
| Other | Terminate immediately with an exception detailing the code |

For a 200 success response the payload is simple json object containing the associated information we need for the input. It has the following format:

```json
{
    "information": "2cba8153f2ff"
}
```

The proxy endpoint has no user authentication and no TLS will be configured. An example request for a proxy bound to localhost:3000 is

```curl
curl 'http://localhost:3000/api/data?input=foo'
```

## Input + Output

There will be exactly 3 command line arguments passed to the application. These are:

1. A file path `input` containing the string set `S`
2. A file path `addresses` containing the set of proxy addresses `A`
3. A file path `output` indicating where the collection output should be written

You may assume:

1. The size of `S` is in the range [0…1000000] and all elements are unique
2. The size of `A` is in the range [1…20] and all elements are unique
3. `input` and `addresses` exist and point to valid data (formats below)
4. No file exists at output but the parent directory does exist
5. `input`, `addresses` and `output` are all absolute paths

The format of `input` is a newline separated list of alphanumeric strings. For example:

```txt
first
second
third

```

The format of addresses is a newline separated list of http addresses. For example:

```txt
http://34.283.112.104:80
http://35.22.112.10:9001
```

The format of the output file should be a newline separated list of pairs associating the input string to its fetched information. The ordering of pairs within the file does not matter. The input and output should be separated with a single space. e.g.

```txt
first 2cba8153f2ff
third 74fb9f6e4bc5
second 6f186e52ca0b

```

## Acceptance criteria

1. A [git bundle](https://stackoverflow.com/questions/11792671/how-to-git-bundle-a-complete-repo/11795549#11795549) of the repo containing your work sent to us
2. A main/master branch containing your application code alongside instructions on how to build, test + run it
3. The application must meet the specification and successfully pass a number of unknown test cases

The things we are judging are:

1. Correctness
2. Readability
3. Unit testing
4. Request throughput (concurrency)

## Using the proxy image

The proxy image (wsd-proxy-test.tar) is a docker image bundled as a tarball. It can be loaded using

```bash
docker load --input /path/to/wsd-proxy-test.tar
```

and then run with default setup (used for our tests) with

```bash
docker run -p "8080:8080" wsd-proxy-test:latest
```

where the http endpoint is bound to port 8080 on the docker host. You can manually set its responses for testing purposes, this is done via an environment variable like so:

```bash
docker run -p "8080:8080" \
  -e "RESPONSE_SEQUENCE=200;2cba8153f2ff;1000|404;;200" \
  wsd-proxy-test:latest
```

where this example response sequence `200;2cba8153f2ff;1000|404;;200` contains 2 responses, the first (`200;2cba8153f2ff;1000`) is a http 200 response with payload `{"information":"2cba8153f2ff"}` which is returned after 1000ms. The second (`404;;200`) is a http 404 response returned after 200ms. You can make this response sequence as long as you’d like. If you send more requests than the length of the sequence it cycles so the responses are repeated indefinitely.

**Hint**
Restart the docker image if at any time you've exceeded the number of concurrent requests. You can (and probably should) run more than one image to simulate multiple proxies.