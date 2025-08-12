from typing import List

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    артикул: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    назва: Mapped[str] = mapped_column(String(255))
    відділ: Mapped[int] = mapped_column(BigInteger)
    група: Mapped[str] = mapped_column(String(100))
    кількість: Mapped[str] = mapped_column(String(50))
    відкладено: Mapped[int] = mapped_column(Integer, default=0)

class SavedList(Base):
    __tablename__ = 'saved_lists'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_name: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    items: Mapped[List["SavedListItem"]] = relationship(back_populates="saved_list", cascade="all, delete-orphan")

class SavedListItem(Base):
    __tablename__ = 'saved_list_items'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(ForeignKey('saved_lists.id'))
    article_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)
    saved_list: Mapped["SavedList"] = relationship(back_populates="items")

# --- НОВА ТАБЛИЦЯ ДЛЯ ТИМЧАСОВИХ СПИСКІВ ("КОШИКІВ") ---
class TempList(Base):
    __tablename__ = 'temp_lists'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer)

    # Зв'язок з товаром, щоб отримувати інформацію про нього (наприклад, відділ)
    product: Mapped["Product"] = relationship()