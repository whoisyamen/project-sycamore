"""Offline regression tests for conservative headline-location evidence."""
import unittest
from unittest.mock import patch
from sycamore_ingest import normalizer


class LocationSafetyTests(unittest.TestCase):
    def test_only_explicit_locus_not_names_products_streets_or_actors(self):
        titles = [
            "Lindsay Clancy murder trial grips viewers",
            "Cyber attack on Paris Hilton's account",
            "Cyber attack in London Road shop",
            "Rockwell Automation OTTO Fleet Manager",
            "Unpatched Magento and Adobe Commerce Zero-Day",
            "Ransomware can teach us a lesson",
            "Attacks in Moscow, Kyiv and Paris",
            "Troops arrive in Washington",
            "Troops arrive in Plymouth",
            "Envoys visit Moscow and Kyiv",
            "Russia hits Ukrainian security headquarters",
            "Europe sabotage: Russia is the chief suspect",
            "DoJ corrects China hacking claim, U.S. agencies were targets",
            "Japan sees risk to Hormuz shipping",  # no explicit incident locus
            "Gold moving out of North America",
        ]
        with patch('urllib.request.urlopen', side_effect=AssertionError('no geocoding network')):
            for title in titles:
                with self.subTest(title=title):
                    self.assertIsNone(normalizer._geocode_from_title(title))
                    article = {'title': title, 'language': 'English', '_rss_topic': 'cyber',
                               'url': 'https://example.com/a', 'domain': 'example.com'}
                    self.assertIsNone(normalizer.normalize(article, 1))

    def test_pronoun_and_explicit_country_acronym(self):
        self.assertIsNone(normalizer._geocode_from_title('A breach in us all'))
        self.assertEqual(normalizer._geocode_from_title('A breach in US hospitals')[2], 'US')
        self.assertEqual(normalizer._geocode_from_title('A breach in U.S. hospitals')[2], 'US')

    def test_explicit_regional_locus_over_actor(self):
        geo = normalizer._geocode_from_title('US condemns teen shot dead in West Bank')
        self.assertEqual(geo, (31.9466, 35.3027, 'PS'))
        self.assertIsNone(normalizer._geocode_from_title('Attacks in Moscow and Kyiv'))

    def test_named_country_waterway_loci(self):
        self.assertEqual(
            normalizer._geocode_from_title(
                'Why did USS Lincoln turn up in Thailand looking so rusty?'),
            (13.7563, 100.5018, 'TH'))
        self.assertEqual(
            normalizer._geocode_from_title(
                'Gulf Shipping Traffic Via Hormuz Keeps Below 10-day Average'),
            (26.5667, 56.2528, 'INT'))
        hit = normalizer.resolve_location('Ships queue at the Panama Canal')
        self.assertIsNotNone(hit)
        self.assertEqual((hit['lat'], hit['lon']), (9.08, -79.68))
        # 'to X' alone is not incident-locus evidence; actor + destination abstain.
        self.assertIsNone(normalizer._geocode_from_title(
            'Korea Paving Way to Send Naval Ship to Hormuz, Reports Say'))
        self.assertIsNone(normalizer._geocode_from_title(
            'Japan sees risk to Hormuz shipping'))
        # No locative preposition: headline states no site.
        self.assertIsNone(normalizer._geocode_from_title(
            'Panama Canal Scraps Planned October Draft Cut'))


if __name__ == '__main__':
    unittest.main()
