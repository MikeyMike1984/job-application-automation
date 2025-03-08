# app/utils/proxies.py
from typing import List, Dict, Optional, Iterator
import random
from itertools import cycle

class ProxyManager:
    """Manage and rotate through proxies."""
    
    def __init__(self, proxies: List[str]):
        """Initialize proxy manager.
        
        Args:
            proxies: List of proxy URLs in format 'http://user:pass@host:port'
        """
        self.proxies = proxies
        self._proxy_cycle = cycle(proxies) if proxies else None
        self._formatted_proxies = [self._format_proxy(p) for p in proxies] if proxies else []
        
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Get the next proxy in rotation.
        
        Returns:
            Proxy dict for requests, or None if no proxies configured
        """
        if not self._proxy_cycle:
            return None
        
        proxy_url = next(self._proxy_cycle)
        return self._format_proxy(proxy_url)
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy.
        
        Returns:
            Proxy dict for requests, or None if no proxies configured
        """
        if not self._formatted_proxies:
            return None
        
        return random.choice(self._formatted_proxies)
    
    def get_all_proxies(self) -> List[Dict[str, str]]:
        """Get all formatted proxies.
        
        Returns:
            List of proxy dicts
        """
        return self._formatted_proxies.copy()
    
    @staticmethod
    def _format_proxy(proxy_url: str) -> Dict[str, str]:
        """Format proxy URL into a dictionary for requests.
        
        Args:
            proxy_url: Proxy URL string
            
        Returns:
            Proxy dict with http and https keys
        """
        if proxy_url.startswith('http://') or proxy_url.startswith('https://'):
            return {'http': proxy_url, 'https': proxy_url}
        
        return {'http': f'http://{proxy_url}', 'https': f'http://{proxy_url}'}