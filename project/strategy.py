from abc import ABC, abstractmethod
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
