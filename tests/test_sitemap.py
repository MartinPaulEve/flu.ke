from apps.staticgen.sitemap import build_robots, build_sitemap


def test_sitemap_lists_absolute_urls():
    xml = build_sitemap(["/", "/news/", "/discography/fluke/risotto/"], "https://flu.ke")
    assert "<loc>https://flu.ke/</loc>" in xml
    assert "<loc>https://flu.ke/news/</loc>" in xml
    assert "<loc>https://flu.ke/discography/fluke/risotto/</loc>" in xml
    assert "<urlset" in xml and "</urlset>" in xml


def test_sitemap_does_not_double_slash():
    xml = build_sitemap(["/news/"], "https://flu.ke/")
    assert "https://flu.ke//news/" not in xml


def test_robots_allows_all_and_links_sitemap():
    robots = build_robots("https://flu.ke")
    assert "User-agent: *" in robots
    assert "Sitemap: https://flu.ke/sitemap.xml" in robots
