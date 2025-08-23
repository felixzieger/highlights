#!/usr/bin/env python3
"""
Find and add missing ISBNs to book posts using multiple APIs.
"""

import re
import time
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import requests
from urllib.parse import quote

class ISBNFinder:
    """Find ISBNs using multiple book APIs."""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BookISBNFinder/1.0)'
        })
    
    def search_openlibrary(self, title: str, author: str = "") -> Optional[str]:
        """Search OpenLibrary API for ISBN."""
        # Clean title - remove subtitle after colon
        clean_title = title.split(':')[0].strip()
        
        queries = []
        if author:
            # Try full search first
            queries.append(f"{clean_title} {author}")
            # Try title only as fallback
            queries.append(clean_title)
        else:
            queries.append(clean_title)
        
        for query in queries:
            url = f"https://openlibrary.org/search.json"
            params = {
                'q': query,
                'fields': 'title,author_name,isbn,first_publish_year',
                'limit': 10
            }
            
            try:
                response = self.session.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    for doc in data.get('docs', []):
                        # Check if title matches reasonably well
                        doc_title = doc.get('title', '').lower()
                        if not self._title_match(clean_title.lower(), doc_title):
                            continue
                        
                        # Check author if provided
                        if author and 'author_name' in doc:
                            if not self._author_match(author, doc['author_name']):
                                continue
                        
                        # Get ISBN-13 preferably, otherwise ISBN-10
                        if 'isbn' in doc and doc['isbn']:
                            for isbn in doc['isbn']:
                                if self._is_valid_isbn13(isbn):
                                    return isbn
                            # Fallback to first ISBN if no ISBN-13
                            for isbn in doc['isbn']:
                                if self._is_valid_isbn(isbn):
                                    return isbn
            except Exception as e:
                print(f"  OpenLibrary error: {e}")
        
        return None
    
    def search_google_books(self, title: str, author: str = "") -> Optional[str]:
        """Search Google Books API for ISBN."""
        clean_title = title.split(':')[0].strip()
        
        query = f"intitle:{clean_title}"
        if author:
            # Use first author if multiple
            first_author = author.split(',')[0].strip()
            query += f" inauthor:{first_author}"
        
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            'q': query,
            'maxResults': 10,
            'printType': 'books'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('items', []):
                    volume_info = item.get('volumeInfo', {})
                    
                    # Check title match
                    vol_title = volume_info.get('title', '').lower()
                    if not self._title_match(clean_title.lower(), vol_title):
                        continue
                    
                    # Check author if provided
                    if author and 'authors' in volume_info:
                        if not any(self._author_match(author, [a]) for a in volume_info['authors']):
                            continue
                    
                    # Get ISBN
                    identifiers = volume_info.get('industryIdentifiers', [])
                    
                    # Prefer ISBN-13
                    for identifier in identifiers:
                        if identifier.get('type') == 'ISBN_13':
                            return identifier.get('identifier')
                    
                    # Fallback to ISBN-10
                    for identifier in identifiers:
                        if identifier.get('type') == 'ISBN_10':
                            isbn10 = identifier.get('identifier')
                            # Convert to ISBN-13
                            return self._isbn10_to_isbn13(isbn10)
        except Exception as e:
            print(f"  Google Books error: {e}")
        
        return None
    
    def _title_match(self, search_title: str, found_title: str) -> bool:
        """Check if titles match reasonably well."""
        # Normalize titles
        search_title = re.sub(r'[^\w\s]', '', search_title).lower()
        found_title = re.sub(r'[^\w\s]', '', found_title).lower()
        
        # Exact match
        if search_title == found_title:
            return True
        
        # One contains the other
        if search_title in found_title or found_title in search_title:
            return True
        
        # Word overlap (at least 80% of search words present)
        search_words = set(search_title.split())
        found_words = set(found_title.split())
        if search_words and found_words:
            overlap = len(search_words & found_words) / len(search_words)
            return overlap >= 0.8
        
        return False
    
    def _author_match(self, search_author: str, found_authors: List[str]) -> bool:
        """Check if author matches any in the list."""
        # Handle multiple authors in search
        search_authors = [a.strip() for a in re.split(r'[,;&]', search_author)]
        
        for s_author in search_authors:
            s_author_lower = s_author.lower()
            s_author_parts = set(s_author_lower.split())
            
            for f_author in found_authors:
                f_author_lower = f_author.lower()
                f_author_parts = set(f_author_lower.split())
                
                # Check if last names match (usually the most important part)
                if s_author_parts & f_author_parts:
                    return True
        
        return False
    
    def _is_valid_isbn(self, isbn: str) -> bool:
        """Check if string is a valid ISBN."""
        isbn = re.sub(r'[^0-9X]', '', isbn.upper())
        return len(isbn) in [10, 13]
    
    def _is_valid_isbn13(self, isbn: str) -> bool:
        """Check if string is a valid ISBN-13."""
        isbn = re.sub(r'[^0-9]', '', isbn)
        return len(isbn) == 13
    
    def _isbn10_to_isbn13(self, isbn10: str) -> str:
        """Convert ISBN-10 to ISBN-13."""
        isbn10 = re.sub(r'[^0-9X]', '', isbn10.upper())
        if len(isbn10) != 10:
            return isbn10
        
        # Remove check digit and add 978 prefix
        isbn13 = '978' + isbn10[:-1]
        
        # Calculate new check digit
        total = sum(int(digit) * (1 if i % 2 == 0 else 3) 
                   for i, digit in enumerate(isbn13))
        check = (10 - (total % 10)) % 10
        
        return isbn13 + str(check)
    
    def find_isbn(self, title: str, author: str = "") -> Optional[str]:
        """Try multiple sources to find ISBN."""
        print(f"  Searching: {title} by {author or 'Unknown'}")
        
        # Try OpenLibrary first
        isbn = self.search_openlibrary(title, author)
        if isbn:
            print(f"  ✓ Found via OpenLibrary: {isbn}")
            return isbn
        
        time.sleep(self.delay)
        
        # Try Google Books
        isbn = self.search_google_books(title, author)
        if isbn:
            print(f"  ✓ Found via Google Books: {isbn}")
            return isbn
        
        print(f"  ✗ No ISBN found")
        return None


def parse_front_matter(content: str) -> Tuple[Dict, str]:
    """Parse YAML front matter from markdown content."""
    if not content.startswith('---'):
        return {}, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    try:
        front_matter = yaml.safe_load(parts[1])
        return front_matter or {}, '---'.join(parts[2:])
    except yaml.YAMLError:
        # Fallback to simple parsing
        front_matter = {}
        for line in parts[1].strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                value = value.strip().strip('"')
                front_matter[key.strip()] = value
        return front_matter, '---'.join(parts[2:])


def update_post_with_isbn(file_path: Path, isbn: str) -> None:
    """Update post file with ISBN."""
    content = file_path.read_text(encoding='utf-8')
    front_matter, body = parse_front_matter(content)
    
    # Add bookshop_id
    front_matter['bookshop_id'] = isbn
    
    # Rebuild content
    new_content = '---\n'
    
    # Preserve order of existing fields
    ordered_keys = ['title', 'book', 'author', 'kindle', 'spoilers', 
                   'content_warnings', 'date', 'tags', 'bookshop_id']
    
    for key in ordered_keys:
        if key in front_matter:
            value = front_matter[key]
            if isinstance(value, str) and (key == 'title' or ' ' in str(value)):
                new_content += f'{key}: "{value}"\n'
            else:
                new_content += f'{key}: {value}\n'
    
    # Add any other fields not in ordered list
    for key, value in front_matter.items():
        if key not in ordered_keys:
            if isinstance(value, str) and ' ' in value:
                new_content += f'{key}: "{value}"\n'
            else:
                new_content += f'{key}: {value}\n'
    
    new_content += '---\n' + body
    
    file_path.write_text(new_content, encoding='utf-8')
    print(f"  Updated: {file_path.name}")


def main():
    """Find and add missing ISBNs to posts."""
    posts_dir = Path('posts')
    if not posts_dir.exists():
        print("Error: posts directory not found")
        return
    
    # Find posts missing bookshop_id
    missing_isbn_posts = []
    
    for post_file in sorted(posts_dir.glob('*.md')):
        content = post_file.read_text(encoding='utf-8')
        front_matter, _ = parse_front_matter(content)
        
        if not front_matter.get('bookshop_id'):
            missing_isbn_posts.append((post_file, front_matter))
    
    if not missing_isbn_posts:
        print("All posts have ISBNs!")
        return
    
    print(f"Found {len(missing_isbn_posts)} posts missing ISBNs\n")
    
    finder = ISBNFinder(delay=0.5)  # Be nice to APIs
    updated_count = 0
    
    for post_file, front_matter in missing_isbn_posts:
        title = front_matter.get('title', '').strip('"')
        author = front_matter.get('author', '').strip('"')
        
        if not title:
            continue
        
        print(f"\n📚 {post_file.name}")
        isbn = finder.find_isbn(title, author)
        
        if isbn:
            update_post_with_isbn(post_file, isbn)
            updated_count += 1
        
        # Rate limiting
        time.sleep(finder.delay)
    
    print(f"\n{'='*50}")
    print(f"Summary: Updated {updated_count}/{len(missing_isbn_posts)} posts with ISBNs")


if __name__ == '__main__':
    main()