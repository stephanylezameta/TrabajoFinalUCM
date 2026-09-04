from database.repositories import ProductRepository

_repo = ProductRepository()


def get_products(query=None, destination=None, max_price=None, min_rating=None):
    return _repo.list(query=query, destination=destination, max_price=max_price, min_rating=min_rating)


def search_products(query: str):
    return _repo.list(query=query)


def filter_products(destination=None, max_price=None, min_rating=None):
    return _repo.list(destination=destination, max_price=max_price, min_rating=min_rating)


def get_product(product_id: str):
    return _repo.get(product_id)


def get_destinations():
    return _repo.destinations()
