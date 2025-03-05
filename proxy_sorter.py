import base64
import json
import requests
import socket
import os
import sys
from typing import Optional, Dict, List
from pathlib import Path

class ProxyProcessor:
    def __init__(self, geo_api_url: str, output_dir: str = "output"):
        self.geo_api_url = geo_api_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.proxy_counter = 0

    def get_country_code(self, ip_address: str) -> Optional[str]:
        try:
            ip_address = socket.gethostbyname(ip_address)
            response = requests.get(f'{self.geo_api_url}/{ip_address}', timeout=5)
            response.raise_for_status()
            return response.json().get('countryCode')
        except (socket.gaierror, requests.RequestException) as e:
            print(f"Error resolving {ip_address}: {e}")
            return None

    @staticmethod
    def country_code_to_emoji(country_code: str) -> str:
        return ''.join(chr(ord(letter) + 127397) for letter in country_code.upper())

    def process_vmess(self, proxy: str) -> Optional[tuple[str, str]]:
        try:
            base64_str = proxy.split('://')[1]
            base64_str = base64_str + '=' * (4 - len(base64_str) % 4)
            decoded_str = base64.b64decode(base64_str).decode('utf-8')
            proxy_json = json.loads(decoded_str)
            ip_address = proxy_json['add']
            country_code = self.get_country_code(ip_address)
            if not country_code:
                return None
            flag_emoji = self.country_code_to_emoji(country_code)
            self.proxy_counter += 1
            remarks = f"{flag_emoji}{country_code}_{self.proxy_counter}_@Surfboardv2ray"
            proxy_json['ps'] = remarks
            encoded_str = base64.b64encode(json.dumps(proxy_json).encode('utf-8')).decode('utf-8')
            return f"vmess://{encoded_str}", country_code
        except Exception as e:
            print(f"Error processing vmess: {e}")
            return None

    def process_vless(self, proxy: str) -> Optional[tuple[str, str]]:
        try:
            ip_address = proxy.split('@')[1].split(':')[0]
            country_code = self.get_country_code(ip_address)
            if not country_code:
                return None
            flag_emoji = self.country_code_to_emoji(country_code)
            self.proxy_counter += 1
            remarks = f"{flag_emoji}{country_code}_{self.proxy_counter}_@Surfboardv2ray"
            processed_proxy = proxy.split('#')[0] + '#' + remarks
            return processed_proxy, country_code
        except Exception as e:
            print(f"Error processing vless: {e}")
            return None

    def process_subscription(self, url: str, countries: List[str]) -> Dict[str, List[str]]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            proxies = response.text.splitlines()
        except requests.RequestException as e:
            print(f"Error fetching subscription {url}: {e}")
            return {}

        country_proxies = {country: [] for country in countries}
        for proxy in proxies:
            proxy = proxy.strip()
            if not proxy:
                continue
            if proxy.startswith('vmess://'):
                result = self.process_vmess(proxy)
            elif proxy.startswith('vless://'):
                result = self.process_vless(proxy)
            else:
                continue
            if result:
                proxy_str, country = result
                if country in country_proxies:
                    country_proxies[country].append(proxy_str)
        return country_proxies

def main(subscription_urls: List[str], countries: str):
    geo_api_url = os.getenv('GET_IPGEO', 'http://ip-api.com/json')
    processor = ProxyProcessor(geo_api_url)
    countries_list = [c.strip().upper() for c in countries.split(',') if c.strip()]
    
    all_results = {}
    for url in subscription_urls:
        result = processor.process_subscription(url, countries_list)
        for country, proxies in result.items():
            if country not in all_results:
                all_results[country] = []
            all_results[country].extend(proxies)
    
    for country, proxies in all_results.items():
        if proxies:
            with open(processor.output_dir / f"{country}.txt", 'w') as f:
                f.write('\n'.join(proxies) + '\n')

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python proxy_sorter.py <subscription_urls> <countries>")
        print("Multiple URLs should be space-separated within quotes")
        sys.exit(1)
    subscription_urls = sys.argv[1].split()
    countries = sys.argv[2]
    main(subscription_urls, countries)