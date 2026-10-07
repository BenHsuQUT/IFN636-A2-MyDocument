from abc import ABC, abstractmethod
from project.models import User


class UserCreator(ABC):
    @abstractmethod
    def create_user(self, username, email):
        """Create a user object with the appropriate role."""
        pass

    def register_user(self, username, email, password):
        user = self.create_user(username, email)
        user.set_password(password)
        return user


class RegularUserCreator(UserCreator):
    def create_user(self, username, email):
        return User(
            username=username,
            email=email,
            role="user"
        )


class AdminUserCreator(UserCreator):
    def create_user(self, username, email):
        return User(
            username=username,
            email=email,
            role="admin"
        )

