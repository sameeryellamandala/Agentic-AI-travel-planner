"""Regression cases taken from the irrelevant results shown in the UI."""

import pytest
from services.wikipedia_service import relevant_article

GOA = {"title": "Goa", "coordinates": [{"lat": 15.5, "lon": 73.83}]}


@pytest.mark.parametrize(
    ("title", "extract"),
    [
        (
            "Ancol Dreamland",
            "Ancol Dreamland is a resort destination in Jakarta, Indonesia.",
        ),
        (
            "Tourism in Indonesia",
            "Tourism in Indonesia is an important part of its economy.",
        ),
        (
            "Tourism in India by state",
            "Goa is one of many Indian states popular for tourism.",
        ),
        (
            "Marketplace",
            "A marketplace is a location where people gather to buy provisions.",
        ),
        ("Goa Gil", "Goa Gil was an American musician, DJ, and party organizer."),
        (
            "Hippie",
            "A hippie is someone associated with a counterculture and Goa trance.",
        ),
    ],
)
def test_unrelated_or_generic_pages_are_not_attractions(title, extract):
    assert not relevant_article({"title": title, "extract": extract}, GOA, "places")


def test_local_attraction_and_coordinates_are_accepted():
    assert relevant_article(
        {
            "title": "Fort Aguada",
            "extract": "Fort Aguada is a seventeenth-century fort in Goa.",
        },
        GOA,
        "places",
    )
    assert relevant_article(
        {
            "title": "Nearby Beach",
            "extract": "A sandy beach.",
            "coordinates": [{"lat": 15.4, "lon": 73.8}],
        },
        GOA,
        "places",
    )
    assert not relevant_article(
        {
            "title": "Distant Beach",
            "extract": "A sandy beach.",
            "coordinates": [{"lat": -6.1, "lon": 106.8}],
        },
        GOA,
        "places",
    )


@pytest.mark.parametrize(
    ("title", "extract"),
    [
        ("Go Goa Gone", "Go Goa Gone is an Indian film about a trip to Goa."),
        ("Indian annexation of Goa", "A military operation by Indian armed forces."),
        ("Goa", "Goa is a state on the western coast of India."),
        (
            "Afghan cuisine",
            "Afghan cuisine consists of dishes and drinks from Afghanistan.",
        ),
        ("Bread", "Bread is a baked food product."),
    ],
)
def test_food_must_be_a_dish_not_a_film_or_overview(title, extract):
    assert not relevant_article(
        {"title": title, "extract": extract}, GOA, "food", cuisine_linked=True
    )


def test_local_dish_and_cuisine_page_evidence():
    assert relevant_article(
        {"title": "Bebinca", "extract": "Bebinca is a layered cake from Goa."},
        GOA,
        "food",
    )
    assert relevant_article(
        {"title": "Vindaloo", "extract": "Vindaloo is an Indian curry dish."},
        GOA,
        "food",
        cuisine_linked=True,
    )
    assert not relevant_article(
        {"title": "Unrelated curry", "extract": "A curry dish from another country."},
        GOA,
        "food",
    )
