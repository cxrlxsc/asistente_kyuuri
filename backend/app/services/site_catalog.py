from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Site:
    display_name: str
    home: str
    search: str                    # {q} se reemplaza por lo buscado, ya codificado
    aliases: tuple[str, ...]       # normalizados (sin acentos, minúsculas)


# Sitios donde puede buscar. Agrega los tuyos aquí.
SITES: dict[str, Site] = {
    "youtube": Site("YouTube", "https://www.youtube.com/",
                    "https://www.youtube.com/results?search_query={q}",
                    ("youtube", "yt", "you tube", "el youtube")),
    "youtube_music": Site("YouTube Music", "https://music.youtube.com/",
                          "https://music.youtube.com/search?q={q}",
                          ("youtube music", "yt music", "music youtube")),
    "wikipedia": Site("Wikipedia", "https://es.wikipedia.org/",
                      "https://es.wikipedia.org/w/index.php?search={q}",
                      ("wikipedia", "wiki")),
    "github": Site("GitHub", "https://github.com/",
                   "https://github.com/search?q={q}",
                   ("github", "git hub")),
    "maps": Site("Google Maps", "https://www.google.com/maps",
                 "https://www.google.com/maps/search/{q}",
                 ("maps", "google maps", "mapas", "el mapa")),
    "netflix": Site("Netflix", "https://www.netflix.com/",
                    "https://www.netflix.com/search?q={q}",
                    ("netflix",)),
    "amazon": Site("Amazon", "https://www.amazon.com/",
                   "https://www.amazon.com/s?k={q}",
                   ("amazon",)),
    "x": Site("X", "https://x.com/", "https://x.com/search?q={q}", ("x", "twitter")),
}


def search_url(site_key: str, query: str) -> str:
    site = SITES[site_key]
    return site.search.replace("{q}", quote_plus(query)) if query else site.home


def site_aliases() -> list[tuple[str, str]]:
    pairs = [(alias, key) for key, site in SITES.items() for alias in site.aliases]
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)
