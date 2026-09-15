"""Mapa de destinos → enlaces de oferta reales de TUI.

Cada recomendación («Ver opciones») debe llevar al usuario a una oferta concreta
de TUI para ese destino, no a la home genérica. Este módulo centraliza esa
correspondencia:

- La clave es el nombre del destino normalizado (minúsculas, sin acentos), igual
  que la que usa ``components.assets`` para las fotos, de modo que se toleran
  variantes cooficiales/municipales que devuelve el motor.
- El valor es el enlace de oferta principal del destino.
- Los destinos sin oferta disponible se marcan con ``NA`` (``None``): la CTA
  cae entonces a un enlace de respaldo (búsqueda en TUI para ese destino, o la
  home si tampoco procede).

Cuando un destino tiene varias ofertas, se toma la primera de la lista como
enlace principal (la CTA es única por tarjeta). El resto queda documentado en
``_OFFER_LINKS_ALL`` por si en el futuro se quiere ofrecer más de una.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import quote

# Enlace genérico de respaldo (home de TUI).
FALLBACK_URL = "https://es.tui.com/es/"


def _normalize_key(text: str) -> str:
    """Minúsculas + sin acentos + solo alfanumérico, igual que components.assets."""
    plain = unicodedata.normalize("NFKD", str(text).lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in plain).strip()


# Alias: nombres que el motor puede devolver (cooficial, municipio, provincia)
# mapeados a la clave normalizada del destino canónico de este mapa.
_DESTINATION_ALIASES: dict[str, str] = {
    "eivissa": "ibiza",
    "santa cruz de tenerife": "tenerife",
    "palma": "mallorca",
    "palma de mallorca": "mallorca",
    "donostia san sebastian": "san sebastian",
    "las palmas de gran canaria": "gran canaria",
    "alicante alacant": "alicante",
    "alacant": "alicante",
    "cancun": "cancun",
    "dubai": "dubai",
}


# Todas las ofertas por destino (nombre canónico → lista de URLs).
# ``None`` como único valor significa que no hay oferta disponible (NA).
_OFFER_LINKS_ALL: dict[str, list[str] | None] = {
    "Algarve": [
        "https://viajeonline.es.tui.com/es/idea/54947386/el-algarve-a-tu-aire?tripId=15",
    ],
    "Alicante": None,
    "Antalya": [
        "https://viajeonline.es.tui.com/es/idea/53902762/-costa-licia-y-egeo-a-tu-aire?tripId=211",
        "https://viajeonline.es.tui.com/es/idea/56863663/antalya-en-familia?tripId=6",
        "https://viajeonline.es.tui.com/es/idea/57288233/joyas-de-turquia-y-playa-opcion-antalya?tripId=19",
        "https://viajeonline.es.tui.com/es/idea/50008911/fly-drive-perlas-del-sur-de-turquia?tripId=2",
        "https://viajeonline.es.tui.com/es/idea/49012521/costa-turca-antalya-5-noches?tripId=108",
        "https://viajeonline.es.tui.com/es/idea/49012143/costa-turca-antalya-7-noches?tripId=99",
        "https://viajeonline.es.tui.com/es/idea/50010168/fly-drive-turquia-monumental-?tripId=11",
    ],
    "Bali": [
        "https://es.tui.com/es/tours/china-milenaria-y-bali/7848/",
        "https://es.tui.com/es/tours/descubriendo-java-y-bali/pk_6717/",
        "https://es.tui.com/es/tours/sur-de-india-kerala-tamil-nadu-y-maldivas/pk_6954/",
        "https://es.tui.com/es/tours/japon-clasico-y-bali/pk_7136/",
        "https://viajeonline.es.tui.com/es/idea/49000602/-singapur-kuala-lumpur-ubud-y-bali",
        "https://es.tui.com/es/tours/lo-mejor-de-bali-y-maldivas/pk_6217/",
        "https://es.tui.com/es/tours/ciudad-prohibida-y-bali/pk_7669/",
        "https://es.tui.com/es/tours/bali-fascinante/pk_5865/",
        "https://es.tui.com/es/tours/fly-y-drive-sudafrica-salvaje/pk_7239/",
        "https://es.tui.com/es/tours/lo-mejor-de-bali-y-gili/pk_6126/",
        "https://es.tui.com/es/tours/bali-isla-de-los-dioses-y-maldivas/pk_5890/",
        "https://es.tui.com/es/tours/super-japon-y-bali/pk_7127/",
        "https://es.tui.com/es/tours/bali-isla-de-los-dioses-y-ubud/pk_5874/",
        "https://es.tui.com/es/tours/japon-fascinante-y-bali/pk_6036/",
        "https://es.tui.com/es/tours/bali-isla-de-los-dioses/pk_5889/",
        "https://es.tui.com/es/tours/bali-isla-de-los-dioses-y-gili/pk_5901/",
        "https://es.tui.com/es/tours/china-imperial-y-bali/pk_7852/",
        "https://es.tui.com/es/tours/lo-mejor-de-bali/pk_5635/",
        "https://es.tui.com/es/tours/bali-fascinante-e-islas-gili/pk_5919/",
        "https://es.tui.com/es/tours/borneo-indonesio-kalimantan-y-bali/pk_5886/",
        "https://es.tui.com/es/tours/sur-de-india-kerala-y-tamil-nadu/pk_6823/",
        "https://es.tui.com/es/tours/bali-esencial/pk_6677/",
        "https://es.tui.com/es/tours/bali-fascinante-y-maldivas/pk_5876/",
    ],
    "Barcelona": [
        "https://es.tui.com/es/tours/laponia-pre-puente-de-diciembre-en-yllaes-salida-desde-barcelona/pk_7649/",
        "https://es.tui.com/es/tours/laponia-puente-de-diciembre-en-levi-salida-desde-barcelona/pk_7650/",
        "https://viajeonline.es.tui.com/es/idea/52788891/delicias-de-tunez-desde-barcelona?tripId=8",
        "https://viajeonline.es.tui.com/es/idea/52684320/estancia-en-tunez-salidas-viernes-verano?tripId=12",
        "https://es.tui.com/es/tours/laponia-puente-de-diciembre-en-levi-apartamentos-salida-desde-barcelona/pk_7661/",
        "https://es.tui.com/es/tours/laponia-puente-de-diciembre-en-yllaes-salida-desde-barcelona/pk_7657/",
    ],
    "Bilbao": [
        "https://es.tui.com/es/tours/costa-rica-en-pascua-desde-bilbao/pk_7711/",
    ],
    "Cabo Verde": [
        "https://es.tui.com/es/resultados/Cabo%20Verde/",
        "https://viajeonline.es.tui.com/es/idea/59019450/cabo-verde-boa-vista-especial-riu-con-tui?tripId=16",
        "https://viajeonline.es.tui.com/es/idea/12776635/estancia-en-isla-de-sal-cabo-verde",
        "https://viajeonline.es.tui.com/es/idea/59017002/cabo-verde-isla-de-sal-especial-riu-con-tui",
    ],
    "Cancún": [
        "https://viajeonline.es.tui.com/es/idea/37934497/-fly-drive-yucatan-en-libertad",
        "https://viajeonline.es.tui.com/es/idea/34898324/yucatan-y-caribe-mexicano-playa-del-carmen-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/43249191/conoce-ciudad-de-mexico-e-isla-mujeres",
        "https://viajeonline.es.tui.com/es/idea/34899131/yucatan-y-caribe-mexicano-cancun-",
        "https://viajeonline.es.tui.com/es/idea/34898903/yucatan-y-caribe-mexicano-costa-mujeres",
        "https://viajeonline.es.tui.com/es/idea/34896638/yucatan-y-caribe-mexicano-tulum",
        "https://viajeonline.es.tui.com/es/idea/54831336/yucatan-y-riviera-maya-en-navidad-y-fin-de-ano",
        "https://viajeonline.es.tui.com/es/idea/49226157/-fly-drive-gran-ruta-de-yucatan",
        "https://viajeonline.es.tui.com/es/idea/50611094/-fly-drive-caribe-mexicano-en-libertad",
        "https://viajeonline.es.tui.com/es/idea/39166934/maravillas-de-los-mayas",
        "https://viajeonline.es.tui.com/es/idea/30333111/conoce-ciudad-de-mexico-y-holbox",
        "https://viajeonline.es.tui.com/es/idea/41023016/ciudad-de-mexico-y-maravillas-mayas",
        "https://viajeonline.es.tui.com/es/idea/43066593/tierra-maya",
    ],
    "Cerdeña": [
        "https://viajeonline.es.tui.com/es/idea/36987964/-roma-la-ciudad-eterna-y-playa-de-cerdena",
        "https://viajeonline.es.tui.com/es/idea/7690815/-cerdena-a-su-aire",
        "https://es.tui.com/es/tours/cerdena/pk_6723/",
        "https://es.tui.com/es/tours/maravillas-de-cerdena-y-corcega/pk_6750/",
    ],
    "Costa Amalfitana": [
        "https://es.tui.com/es/tours/costa-amalfitana-y-puglia/pk_6743/",
        "https://viajeonline.es.tui.com/es/idea/36983950/la-maravillosa-costa-amalfitana?tripId=1",
        "https://viajeonline.es.tui.com/es/idea/7695783/-napoles-y-costa-amalfitana-a-su-aire",
        "https://viajeonline.es.tui.com/es/idea/59034687/escapada-a-napoles-y-la-costa-amalfitana?tripId=22",
        "https://es.tui.com/es/tours/napoles-y-la-costa-amalfitana/pk_56939950/",
        "https://es.tui.com/es/tours/lo-mejor-de-costa-amalfitana/pk_35140239/",
    ],
    "Costa del Sol": [
        "https://es.tui.com/es/tours/el-salvador-autentico/pk_19394642/",
    ],
    "Creta": [
        "https://es.tui.com/es/resultados/Creta/",
        "https://viajeonline.es.tui.com/es/idea/53901667/-creta-a-tu-aire?tripId=202",
        "https://es.tui.com/es/tours/china-secreta/pk_7431/",
        "https://es.tui.com/es/tours/francia-secreta-y-la-alsacia/pk_35056590/",
        "https://viajeonline.es.tui.com/es/idea/58843305/atenas-santorini-y-creta?tripId=1",
        "https://viajeonline.es.tui.com/es/idea/58598934/mykonos-santorini-y-creta?tripId=17",
        "https://viajeonline.es.tui.com/es/idea/48788520/-crucero-mediterraneo-oriental-y-estambul",
    ],
    "Cádiz": None,
    "Córdoba": None,
    "Dubái": [
        "https://viajeonline.es.tui.com/es/idea/35466531/esencias-arabigas-dubai-y-muscat",
        "https://viajeonline.es.tui.com/es/idea/49186029/escapada-a-dubai?tripId=192",
        "https://viajeonline.es.tui.com/es/idea/23214708/descubre-dubai-y-abu-dhabi?tripId=3",
        "https://viajeonline.es.tui.com/es/idea/49090491/dubai-7-noches-?tripId=107",
        "https://es.tui.com/es/tours/dubai-y-maldivas/pk_7277/",
        "https://viajeonline.es.tui.com/es/idea/32416941/crucero-perlas-de-arabia",
    ],
    "Fuerteventura": [
        "https://es.tui.com/es/resultados/Fuerteventura/",
        "https://viajeonline.es.tui.com/es/idea/47627139/fuerteventura-7-noches-con-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/47625720/fuerteventura-7-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/47445234/fuerteventura-5-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/37152130/-luna-de-miel-en-lanzarote-y-fuerteventura",
        "https://viajeonline.es.tui.com/es/idea/49449414/-fly-drive-fuerteventura",
        "https://viajeonline.es.tui.com/es/idea/47445915/fuerteventura-5-noches-con-coche-de-alquiler",
    ],
    "Gran Canaria": [
        "https://es.tui.com/es/resultados/Gran%20Canaria/",
        "https://viajeonline.es.tui.com/es/idea/36102928/-tenerife-y-gran-canaria",
        "https://viajeonline.es.tui.com/es/idea/49449765/crucero-canarias-y-madeira",
        "https://viajeonline.es.tui.com/es/idea/47062965/gran-canaria-5-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/47066838/gran-canaria-7-noches-con-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/47065596/gran-canaria-7-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/47064588/gran-canaria-5-noches-con-coche-de-alquiler",
    ],
    "Granada": [
        "https://viajeonline.es.tui.com/es/idea/13037581/granada",
        "https://es.tui.com/es/tours/ruta-colonial-de-centroamerica/pk_43189023/",
        "https://viajeonline.es.tui.com/es/idea/37077445/costa-rica-y-nicaragua",
        "https://es.tui.com/es/tours/nicaragua-legendaria-y-corn-island/pk_30401268/",
    ],
    "Hurghada": [
        "https://es.tui.com/es/tours/tesoros-de-egipto-y-hurghada-salida-martes-y-jueves/pk_7389/",
        "https://viajeonline.es.tui.com/es/idea/49176255/hurghada-7-noches?tripId=1",
        "https://es.tui.com/es/tours/tesoros-de-egipto-y-hurghada-salida-lunes-y-sabado/pk_7390/",
        "https://viajeonline.es.tui.com/es/idea/49095492/hurghada-5-noches?tripId=167",
        "https://es.tui.com/es/tours/tesoros-de-egipto-y-hurghada-salida-miercoles/pk_7380/",
        "https://es.tui.com/es/tours/tesoros-de-egipto-y-hurghada-salida-domingo/pk_7387/",
    ],
    "Ibiza": [
        "https://es.tui.com/es/resultados/Ibiza/",
        "https://viajeonline.es.tui.com/es/idea/46749894/ibiza-5-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/37154989/luna-de-miel-en-ibiza-y-formentera",
        "https://viajeonline.es.tui.com/es/idea/46754106/ibiza-5-noches-con-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/46756809/ibiza-7-noches-con-coche-de-alquilerr",
    ],
    "Lanzarote": [
        "https://viajeonline.es.tui.com/es/idea/47427483/lanzarote-7-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/49449765/crucero-canarias-y-madeira",
        "https://viajeonline.es.tui.com/es/idea/37152130/-luna-de-miel-en-lanzarote-y-fuerteventura",
        "https://viajeonline.es.tui.com/es/idea/47342880/lanzarote-5-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/47428308/lanzarote-7-noches-con-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/47343723/lanzarote-5-noches-con-coche-de-alquiler",
    ],
    "Madrid": [
        "https://viajeonline.es.tui.com/es/idea/52788666/delicias-de-tunez-desde-madrid?tripId=5",
        "https://es.tui.com/es/tours/puente-de-diciembre-en-levi/pk_6517/",
        "https://es.tui.com/es/tours/nueva-york-en-semana-santa/pk_7672/",
        "https://es.tui.com/es/tours/costa-rica-en-fin-de-ano/pk_7291/",
        "https://es.tui.com/es/tours/puente-de-diciembre-en-levi-apartamentos/pk_6518/",
        "https://es.tui.com/es/tours/puente-de-diciembre-en-yllaes/pk_6514/",
        "https://viajeonline.es.tui.com/es/idea/52683846/estancia-en-tunez-salidas-viernes-verano?tripId=10",
    ],
    "Maldivas": [
        "https://es.tui.com/es/tours/ruta-masai-y-maldivas/pk_5655/",
        "https://es.tui.com/es/tours/sur-de-india-kerala-tamil-nadu-y-maldivas/pk_6954/",
        "https://es.tui.com/es/tours/colores-del-rajastan-y-maldivas/pk_7668/",
        "https://es.tui.com/es/tours/reserva-privada-de-sabi-sabi-opcion-1-y-maldivas/pk_6904/",
        "https://es.tui.com/es/tours/super-thai-y-maldivas-salida-lunes/pk_7043/",
        "https://es.tui.com/es/tours/tesoros-de-sudafrica-y-maldivas/pk_7836/",
        "https://es.tui.com/es/tours/safari-ngorongoro-y-maldivas/pk_6124/",
        "https://es.tui.com/es/tours/descubre-vietnam-y-maldivas/pk_7821/",
        "https://es.tui.com/es/tours/tesoros-de-sudafrica-y-maldivas-2027/pk_7837/",
        "https://es.tui.com/es/tours/maldivas-u-especial-riu/pk_7701/",
        "https://es.tui.com/es/tours/reserva-privada-sudafrica-y-maldivas-opcion-2/pk_6025/",
        "https://es.tui.com/es/tours/lo-mejor-de-bali-y-maldivas/pk_6217/",
        "https://es.tui.com/es/tours/kenia-express-y-maldivas/pk_5631/",
        "https://es.tui.com/es/tours/sri-lanka-fascinante-y-maldivas/pk_7696/",
        "https://es.tui.com/es/tours/tonkin-y-maldivas/pk_5985/",
        "https://es.tui.com/es/tours/super-japon-y-maldivas/pk_5928/",
        "https://es.tui.com/es/tours/descubre-sri-lanka-y-maldivas/pk_7737/",
        "https://es.tui.com/es/tours/tailandia-fascinante-y-maldivas/pk_6065/",
        "https://es.tui.com/es/tours/sabanas-de-kenia-y-tanzania-y-maldivas/pk_5885/",
        "https://es.tui.com/es/tours/increible-kenia-y-maldivas/pk_6156/",
        "https://es.tui.com/es/tours/contrastes-de-sudafrica-y-maldivas/pk_7817/",
        "https://es.tui.com/es/tours/bali-isla-de-los-dioses-y-maldivas/pk_5890/",
        "https://es.tui.com/es/tours/sri-lanka-express-y-maldivas/pk_5925/",
        "https://es.tui.com/es/tours/china-imperial-y-maldivas/pk_7126/",
        "https://es.tui.com/es/tours/safari-amani-y-maldivas/pk_5857/",
        "https://es.tui.com/es/tours/ciudad-prohibida-y-maldivas/pk_7125/",
    ],
    "Mallorca": [
        "https://es.tui.com/es/resultados/Mallorca/",
        "https://viajeonline.es.tui.com/es/idea/46332134/mallorca",
        "https://viajeonline.es.tui.com/es/idea/46332497/mallorca-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/46333817/mallorca-8-dias-7-noches-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/46333175/mallorca-8-dias-7-noches",
    ],
    "Marrakech": [
        "https://es.tui.com/es/resultados/Marrakech/",
        "https://es.tui.com/es/tours/nomadas-en-el-desierto-del-sur/pk_7160/",
        "https://viajeonline.es.tui.com/es/idea/52072559/fly-drive-oasis-de-marruecos?tripId=31",
        "https://viajeonline.es.tui.com/es/idea/52071668/ruta-de-las-mil-kasbahs-a-tu-aire-fly-drive?tripId=19",
        "https://es.tui.com/es/tours/marruecos-multicolor-u-llegadas-a-marrakech/pk_5969/",
        "https://es.tui.com/es/tours/marruecos-multicolor-or-llegadas-a-marrakech-1/pk_6210/",
        "https://viajeonline.es.tui.com/es/idea/38050359/marrakech-en-pareja",
        "https://viajeonline.es.tui.com/es/idea/51741089/montanas-del-atlas-en-moto?tripId=4",
        "https://es.tui.com/es/tours/contraste-de-marruecos-imperial-y-kasbahs-llegada-marrakech/pk_6221/",
        "https://viajeonline.es.tui.com/es/idea/49172886/escapada-a-marrakech?tripId=166",
        "https://viajeonline.es.tui.com/es/idea/8241865/marrakech",
        "https://es.tui.com/es/tours/marruecos-inedito/pk_6224/",
        "https://viajeonline.es.tui.com/es/idea/29808821/sur-de-marruecos-en-4x4",
    ],
    "Menorca": [
        "https://es.tui.com/es/resultados/Menorca/",
        "https://viajeonline.es.tui.com/es/idea/46765899/menorca-7-noches-con-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/49437681/menorca-en-libertad",
        "https://viajeonline.es.tui.com/es/idea/46764912/menorca-7-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/46759596/menorca-5-noches-con-traslados",
    ],
    "Málaga": [
        "https://es.tui.com/es/tours/laponia-puente-de-diciembre-en-levi-apartamentos-salida-desde-malaga/pk_7662/",
        "https://es.tui.com/es/tours/laponia-puente-de-diciembre-en-yllaes-salida-desde-malaga/pk_7658/",
        "https://es.tui.com/es/tours/laponia-puente-de-diciembre-en-levi-salida-desde-malaga/pk_7652/",
    ],
    "Phuket": [
        "https://es.tui.com/es/tours/super-vietnam-y-phuket/pk_6056/",
        "https://es.tui.com/es/tours/joyas-de-tailandia-y-phuket/pk_6072/",
        "https://es.tui.com/es/tours/japon-fascinante-y-phuket/pk_6053/",
        "https://es.tui.com/es/tours/tailandia-clasica-y-phuket/pk_7110/",
        "https://es.tui.com/es/tours/tailandia-autentica-y-phuket/pk_6978/",
        "https://es.tui.com/es/tours/japon-clasico-y-phuket/pk_7143/",
        "https://es.tui.com/es/tours/paisajes-y-tribus-de-vietnam-y-phuket/pk_7829/",
        "https://es.tui.com/es/tours/super-japon-y-phuket/pk_7132/",
        "https://viajeonline.es.tui.com/es/idea/12297721/-bangkok-y-phuket",
        "https://es.tui.com/es/tours/tonkin-y-phuket/pk_6000/",
        "https://es.tui.com/es/tours/tailandia-fascinante-y-phuket/pk_6061/",
        "https://es.tui.com/es/tours/super-vietnam-camboya-en-vuelo-y-phuket/pk_5920/",
        "https://viajeonline.es.tui.com/es/idea/15763717/estancia-en-phuket",
        "https://es.tui.com/es/tours/descubre-vietnam-y-phuket/pk_7819/",
        "https://es.tui.com/es/tours/tailandia-magica-y-phuket-al-completo/pk_6724/",
        "https://es.tui.com/es/tours/gran-tour-de-tailandia-y-phuket/pk_6086/",
    ],
    "Punta Cana": [
        "https://viajeonline.es.tui.com/es/idea/42108135/-nueva-york-niagara-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/6657201/punta-cana",
        "https://viajeonline.es.tui.com/es/idea/7541196/-nueva-york-orlando-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/14286325/-santo-domingo-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/12296734/luna-de-miel-en-nueva-york-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/41634461/-nueva-york-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/55167365/nueva-york-washington-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/13211452/-orlando-y-punta-cana",
        "https://viajeonline.es.tui.com/es/idea/17541202/punta-cana-en-riu-resorts",
        "https://viajeonline.es.tui.com/es/idea/48627895/guatemala-autentica-y-republica-dominicana",
    ],
    "Riviera Maya": [
        "https://viajeonline.es.tui.com/es/idea/39292835/mexico-magico",
        "https://viajeonline.es.tui.com/es/idea/35692894/nueva-york-niagara-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/59234504/mexico-en-dia-de-muertos-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/6516381/-nueva-york-orlando-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/6656565/riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/57071641/mexico-arqueologico",
        "https://viajeonline.es.tui.com/es/idea/48628387/guatemala-autentica-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/12080374/-luna-de-miel-en-nueva-york-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/41633438/-nueva-york-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/36164146/luna-de-miel-en-familia-en-orlando-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/43062885/embrujo-mexicano",
        "https://es.tui.com/es/tours/machu-picchu-y-riviera-maya/pk_6884/",
        "https://viajeonline.es.tui.com/es/idea/39611508/lo-mejor-de-mexico",
        "https://es.tui.com/es/tours/gran-peru-y-riviera-maya/pk_6885/",
        "https://viajeonline.es.tui.com/es/idea/54831336/yucatan-y-riviera-maya-en-navidad-y-fin-de-ano",
        "https://viajeonline.es.tui.com/es/idea/43174386/-aztecas-y-mayas",
        "https://es.tui.com/es/tours/descubre-mexico/pk_6761/",
        "https://viajeonline.es.tui.com/es/idea/33740646/-oeste-clasico-y-caribe",
        "https://viajeonline.es.tui.com/es/idea/41878821/nueva-york-las-vegas-y-riviera-maya",
        "https://viajeonline.es.tui.com/es/idea/30331914/conoce-ciudad-de-mexico-y-riviera-maya",
    ],
    "Rodas": [
        "https://es.tui.com/es/resultados/Rodas/",
    ],
    "San Sebastián": None,
    "Santorini": [
        "https://es.tui.com/es/resultados/Santorini/",
        "https://viajeonline.es.tui.com/es/idea/48752364/mykonos-y-santorini-con-traslados?tripId=7",
        "https://es.tui.com/es/tours/grecia-express-y-santorini/pk_6727/",
        "https://viajeonline.es.tui.com/es/idea/36620626/grecia-clasica-y-santorini-salidas-martes-y-viernes",
        "https://viajeonline.es.tui.com/es/idea/58596252/mykonos-y-santorini?tripId=2",
        "https://es.tui.com/es/tours/romance-en-turquia-e-islas-griegas/pk_7019/",
        "https://viajeonline.es.tui.com/es/idea/36618904/grecia-clasica-y-santorini-salidas-lunes-y-jueves",
        "https://viajeonline.es.tui.com/es/idea/58843305/atenas-santorini-y-creta?tripId=1",
        "https://viajeonline.es.tui.com/es/idea/58598025/mykonos-paros-y-santorini?tripId=13",
        "https://viajeonline.es.tui.com/es/idea/36622102/grecia-clasica-y-santorini-salidas-miercoles-y-domingos",
    ],
    "Sevilla": None,
    "Sicilia": [
        "https://viajeonline.es.tui.com/es/idea/7712871/fly-drive-sicilia-magica?tripId=5",
        "https://es.tui.com/es/tours/sicilia-magica/pk_6714/",
        "https://viajeonline.es.tui.com/es/idea/7710561/-fly-drive-sicilia-clasica?tripId=2",
        "https://viajeonline.es.tui.com/es/idea/7697348/-fly-drive-sicilia-barroca",
        "https://es.tui.com/es/tours/sicilia-mitos-y-leyendas/pk_6057/",
        "https://es.tui.com/es/tours/maravillas-de-sicilia-y-malta/pk_6753/",
    ],
    "Split": [
        "https://viajeonline.es.tui.com/es/idea/44913813/islas-del-sur-adriatico-categoria-deluxe?tripId=14",
        "https://viajeonline.es.tui.com/es/idea/53895802/-croacia-clasica-a-tu-aire?tripId=49",
        "https://es.tui.com/es/tours/encanto-de-los-balcanes/pk_47729877/",
        "https://viajeonline.es.tui.com/es/idea/5990882/f-d-toda-croacia",
        "https://es.tui.com/es/tours/lo-mejor-de-los-balcanes-croacia-bosnia-mostar-y-montenegro-al-completo/pk_6617/",
        "https://viajeonline.es.tui.com/es/idea/56328721/eslovenia-y-croacia-a-tu-aire?tripId=55",
        "https://es.tui.com/es/tours/croacia-maravillosa/pk_47728578/",
        "https://viajeonline.es.tui.com/es/idea/44913435/islas-del-adriatico-sur-categoria-superior?tripId=10",
        "https://viajeonline.es.tui.com/es/idea/44912892/islas-del-sur-adriatico-categoria-estandar?tripId=6",
        "https://viajeonline.es.tui.com/es/idea/58589610/dubrovnik-isla-de-hvar-y-split-a-tu-aire?tripId=16",
    ],
    "Tenerife": [
        "https://es.tui.com/es/resultados/Tenerife/",
        "https://viajeonline.es.tui.com/es/idea/47165004/tenerife-5-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/47192703/tenerife-7-noches-con-coche-de-alquiler-",
        "https://viajeonline.es.tui.com/es/idea/36102928/-tenerife-y-gran-canaria",
        "https://viajeonline.es.tui.com/es/idea/47190327/tenerife-7-noches-con-traslados",
        "https://viajeonline.es.tui.com/es/idea/49449765/crucero-canarias-y-madeira",
        "https://viajeonline.es.tui.com/es/idea/47184075/tenerife-5-noches-con-coche-de-alquiler",
        "https://viajeonline.es.tui.com/es/idea/49445523/-fly-drive-tenerife",
    ],
    "Túnez": [
        "https://viajeonline.es.tui.com/es/idea/48864315/hammamet-5-noches-con-traslados?tripId=30",
        "http://viajeonline.es.tui.com/es/idea/29809796/tunez-inedita",
        "https://es.tui.com/es/tours/tunez-desierto-y-patrimonio/pk_6115/",
        "https://viajeonline.es.tui.com/es/idea/52788666/delicias-de-tunez-desde-madrid?tripId=5",
        "https://viajeonline.es.tui.com/es/idea/52681878/estancia-en-tunez-vuelos-tunisair?tripId=1",
        "https://viajeonline.es.tui.com/es/idea/52788891/delicias-de-tunez-desde-barcelona?tripId=8",
        "https://viajeonline.es.tui.com/es/idea/52684320/estancia-en-tunez-salidas-viernes-verano?tripId=12",
        "https://viajeonline.es.tui.com/es/idea/48865809/monastir-5-noches-con-traslados?tripId=39",
        "https://viajeonline.es.tui.com/es/idea/29809610/tunez-arqueologico",
        "https://viajeonline.es.tui.com/es/idea/49824213/tunez-isla-de-djerba-6-noches",
        "https://es.tui.com/es/tours/esencias-de-tunez/pk_6760/",
        "https://viajeonline.es.tui.com/es/idea/30374162/naturaleza-y-cultura-en-tunez",
        "https://viajeonline.es.tui.com/es/idea/29809313/tunez-a-tu-aire-fly-drive",
        "https://es.tui.com/es/tours/tunez-desierto-y-playa/pk_7162/",
        "https://viajeonline.es.tui.com/es/idea/52683846/estancia-en-tunez-salidas-viernes-verano?tripId=10",
    ],
    "Valencia": None,
}


# Mapa normalizado (clave sin acentos) → URL principal (o None si NA).
_OFFER_LINKS_BY_KEY: dict[str, str | None] = {}
for _name, _urls in _OFFER_LINKS_ALL.items():
    _OFFER_LINKS_BY_KEY[_normalize_key(_name)] = (_urls[0] if _urls else None)


def _search_url(destination: str) -> str:
    """Enlace de búsqueda de TUI para un destino sin oferta concreta (NA)."""
    if not destination:
        return FALLBACK_URL
    return "https://es.tui.com/es/resultados/" + quote(str(destination))


def get_offer_url(destination: str) -> str:
    """Devuelve el enlace de oferta principal de TUI para un destino.

    - Si el destino tiene oferta, devuelve su URL principal.
    - Si el destino existe pero está marcado NA (sin oferta), devuelve una
      búsqueda de TUI para ese destino, de modo que la CTA sigue siendo útil.
    - Si el destino no está en el mapa, cae a una búsqueda de TUI por su nombre.
    """
    if not destination:
        return FALLBACK_URL
    key = _normalize_key(destination)
    key = _DESTINATION_ALIASES.get(key, key)
    if key in _OFFER_LINKS_BY_KEY:
        url = _OFFER_LINKS_BY_KEY[key]
        return url if url else _search_url(destination)
    # Destino desconocido: búsqueda por nombre en TUI (mejor que la home).
    return _search_url(destination)


def get_all_offer_urls(destination: str) -> list[str]:
    """Devuelve todas las ofertas conocidas de un destino (vacío si NA/desconocido)."""
    if not destination:
        return []
    key = _normalize_key(destination)
    key = _DESTINATION_ALIASES.get(key, key)
    for _name, _urls in _OFFER_LINKS_ALL.items():
        if _normalize_key(_name) == key and _urls:
            return list(_urls)
    return []
