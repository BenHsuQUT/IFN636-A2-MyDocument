from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import sqlalchemy as db

class SearchStrategy(ABC):
    @abstractmethod
    def apply(self, query, value):
        pass

class KeywordSearchStrategy(SearchStrategy):
    def apply(self, query, value):
        if not value:
            return query
        keyword = f"%{value}%"
        Document = query.column_descriptions[0]['type']
        return query.filter(
            db.or_(
                Document.title.ilike(keyword),
                Document.notes.ilike(keyword),
                Document.category.ilike(keyword),
                Document.original_filename.ilike(keyword)
            )
        )

class TypeSearchStrategy(SearchStrategy):
    def apply(self, query, value):
        if not value or value == "All Types":
            return query
        
        mapping = {
            "PDF": ["%.pdf"],
            "Word": ["%.doc", "%.docx"],
            "Excel": ["%.xls", "%.xlsx"],
            "Text": ["%.txt"],
            "Image": ["%.png", "%.jpg", "%.jpeg"]
        }
        patterns = mapping.get(value, [])
        if patterns:
            Document = query.column_descriptions[0]['type']
            return query.filter(db.or_(*(Document.original_filename.ilike(p) for p in patterns)))
        return query

class CategorySearchStrategy(SearchStrategy):
    def apply(self, query, value):
        if not value or value == "All Categories":
            return query
        Document = query.column_descriptions[0]['type']
        return query.filter(Document.category == value)

class DateSearchStrategy(SearchStrategy):
    def apply(self, query, value):
        if not value or value == "All Dates":
            return query
        
        now = datetime.utcnow()
        Document = query.column_descriptions[0]['type']
        
        if value == "Today":
            return query.filter(Document.uploaded_at >= datetime(now.year, now.month, now.day))
        elif value == "Last 7 days":
            return query.filter(Document.uploaded_at >= now - timedelta(days=7))
        elif value == "Last 30 days":
            return query.filter(Document.uploaded_at >= now - timedelta(days=30))
        return query

class SizeSearchStrategy(SearchStrategy):
    def apply(self, query, value):
        if not value or value == "All Sizes":
            return query
        
        Document = query.column_descriptions[0]['type']
        if value == "< 1 MB":
            return query.filter(Document.filesize_bytes < 1024 * 1024)
        elif value == "1 MB – 100 MB":
            return query.filter(Document.filesize_bytes >= 1024 * 1024, Document.filesize_bytes < 100 * 1024 * 1024)
        elif value == ">= 100 MB":
            return query.filter(Document.filesize_bytes >= 100 * 1024 * 1024)
        return query

class SearchContext:
    def __init__(self):
        self.strategies = []

    def add(self, strategy: SearchStrategy, value):
        if value:
            self.strategies.append((strategy, value))
        return self

    def execute(self, query):
        for strategy, value in self.strategies:
            query = strategy.apply(query, value)
        return query
