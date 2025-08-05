from sqlalchemy import String, BigInteger, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List

class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    назва: Mapped[str] = mapped_column(String(255), index=True)
    відділ: Mapped[int] = mapped_column(BigInteger)
    група: Mapped[str] = mapped_column(String(100))
    кількість: Mapped[str] = mapped_column(String(50))
    відкладено: Mapped[int] = mapped_column(Integer, default=0)

# --- НОВА ТАБЛИЦЯ ДЛЯ ЗБЕРЕЖЕНИХ ФАЙЛІВ ---
class SavedList(Base):
    __tablename__ = 'saved_lists'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_name: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    # Зв'язок з вмістом списку
    items: Mapped[List["SavedListItem"]] = relationship(back_populates="saved_list")

# --- НОВА ТАБЛИЦЯ ДЛЯ ВМІСТУ КОЖНОГО ФАЙЛУ ---
class SavedListItem(Base):
    __tablename__ = 'saved_list_items'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(ForeignKey('saved_lists.id'))
    article_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)

    # Зв'язок з файлом
    saved_list: Mapped["SavedList"] = relationship(back_populates="items")