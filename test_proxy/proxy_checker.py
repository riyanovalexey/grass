import requests
import concurrent.futures
import time

def check_proxy(proxy):
    url = "https://www.google.com"
    try:
        start_time = time.time()
        response = requests.get(url, proxies={'http': proxy, 'https': proxy}, timeout=10)
        end_time = time.time()
        
        if response.status_code == 200:
            speed = end_time - start_time
            return (True, f"[WORKING] {proxy} - Response time: {speed:.2f} seconds", proxy)
        return (False, f"[FAILED] {proxy} - Bad status code: {response.status_code}", proxy)
    
    except requests.exceptions.RequestException:
        return (False, f"[FAILED] {proxy} - Connection error", proxy)

def main():
    # Read proxies from file (one proxy per line in format ip:port)
    with open('test_proxy/proxy.txt', 'r') as file:
        proxies = [line.strip() for line in file if line.strip()]
    
    # Number of concurrent checks
    max_workers = 10
    
    working_proxies = []
    print("Starting proxy check...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(check_proxy, proxies)
        
        for result in results:
            print(result[1])
            if result[0]:
                working_proxies.append(result[2])
    
    # Update proxy file with only working proxies
    with open('proxy.txt', 'w') as file:
        for proxy in working_proxies:
            file.write(f"{proxy}\n")

if __name__ == "__main__":
    main()