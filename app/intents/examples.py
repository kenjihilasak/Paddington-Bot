"""Canonical intent examples used by embedding-based classification."""

from __future__ import annotations

from app.schemas.bot import IntentType


INTENT_EXAMPLES: dict[IntentType, list[str]] = {
    IntentType.HELP_MENU: [
        "help",
        "show me the menu",
        "what can you do",
        "ayuda",
        "muestrame el menu",
        "que puedes hacer",
    ],
    IntentType.SUMMARY: [
        "show me the latest summary",
        "give me a recap",
        "community overview",
        "quiero un resumen",
        "dame un resumen de la comunidad",
        "muestame el resumen",
    ],
    IntentType.CREATE_EXCHANGE_OFFER: [
        "I want to exchange 300 soles for pounds in Leeds",
        "offering euros and need pounds",
        "post an exchange offer for me",
        "quiero cambiar 300 soles por libras en Leeds",
        "ofrezco euros y necesito libras",
        "publica mi oferta de cambio",
    ],
    IntentType.SEARCH_EXCHANGE_OFFERS: [
        "show me exchange offers for pounds to euros",
        "find people exchanging soles to pounds",
        "search exchange offers",
        "muestrame cambios de libras a euros",
        "busca ofertas de cambio de soles a libras",
        "quiero ver ofertas de cambio",
    ],
    IntentType.CREATE_LISTING: [
        "I'm selling a microwave in Headingley for 25 pounds",
        "post my bike for sale",
        "I want to sell a laptop",
        "vendo un microondas en Headingley por 25 libras",
        "publica mi anuncio para vender una bicicleta",
        "quiero vender mi laptop",
    ],
    IntentType.SEARCH_LISTINGS: [
        "show me listings in Leeds",
        "find bikes for sale",
        "browse listings",
        "muestrame anuncios en Leeds",
        "busca bicicletas en venta",
        "quiero ver publicaciones de venta",
    ],
    IntentType.CREATE_EVENT: [
        "there is a football match on Saturday at 6pm in Hyde Park",
        "post a community meetup next Tuesday",
        "create an event for the workshop",
        "hay un partido el sabado a las 6pm en Hyde Park",
        "publica un evento comunitario para el martes",
        "crea un evento para el taller",
    ],
}
