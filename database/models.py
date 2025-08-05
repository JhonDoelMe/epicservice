from sqlalchemy import String, BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    назва: Mapped[str] = mapped_column(String(255), index=True) # Додамо індекс для швидкого пошуку
    відділ: Mapped[int] = mapped_column(BigInteger)
    група: Mapped[str] = mapped_column(String(100))
    кількість: Mapped[str] = mapped_column(String(50))
    відкладено: Mapped[int] = mapped_column(Integer, default=0) # Змінено на Integer