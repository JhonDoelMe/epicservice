# epicservice/database/models.py

from typing import List

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовий клас для декларативних моделей SQLAlchemy."""
    pass


# НОВА МОДЕЛЬ для зберігання всіх користувачів
class User(Base):
    """Модель, що представляє користувача бота."""
    __tablename__ = 'users'

    # Telegram ID буде первинним ключем
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    # Зв'язки з іншими таблицями
    saved_lists: Mapped[List["SavedList"]] = relationship(back_populates="user")
    temp_list_items: Mapped[List["TempList"]] = relationship(back_populates="user")


class Product(Base):
    """Модель, що представляє товар на складі."""
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    артикул: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    назва: Mapped[str] = mapped_column(String(255))
    відділ: Mapped[int] = mapped_column(BigInteger)
    група: Mapped[str] = mapped_column(String(100))
    кількість: Mapped[str] = mapped_column(String(50))
    відкладено: Mapped[int] = mapped_column(Integer, default=0)


class SavedList(Base):
    """Модель, що представляє збережений список товарів користувача."""
    __tablename__ = 'saved_lists'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # ОНОВЛЕНО: Додано ForeignKey для зв'язку з таблицею users
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    file_name: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    items: Mapped[List["SavedListItem"]] = relationship(back_populates="saved_list", cascade="all, delete-orphan")
    user: Mapped["User"] = relationship(back_populates="saved_lists")


class SavedListItem(Base):
    """Модель, що представляє один пункт у збереженому списку."""
    __tablename__ = 'saved_list_items'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(ForeignKey('saved_lists.id'))
    article_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)

    saved_list: Mapped["SavedList"] = relationship(back_populates="items")


class TempList(Base):
    """Модель, що представляє тимчасовий (поточний) список товарів користувача."""
    __tablename__ = 'temp_lists'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # ОНОВЛЕНО: Додано ForeignKey для зв'язку з таблицею users
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer)

    product: Mapped["Product"] = relationship()
    user: Mapped["User"] = relationship(back_populates="temp_list_items")