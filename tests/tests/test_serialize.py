from __future__ import unicode_literals

import json
import datetime

from django.test import TestCase
from django.utils import timezone

from tests.models import Band, BandMember, Album, Restaurant, Dish, MenuItem, Chef, Wine, Log


class SerializeTest(TestCase):
    def test_serialize(self):
        beatles = Band(name='The Beatles', members=[
            BandMember(name='John Lennon'),
            BandMember(name='Paul McCartney'),
        ])

        expected = {'pk': None, 'albums': [], 'name': 'The Beatles', 'members': [{'pk': None, 'name': 'John Lennon', 'band': None}, {'pk': None, 'name': 'Paul McCartney', 'band': None}]}
        self.assertEqual(expected, beatles.serializable_data())

    def test_serialize_json_with_dates(self):
        beatles = Band(name='The Beatles', members=[
            BandMember(name='John Lennon'),
            BandMember(name='Paul McCartney'),
        ], albums=[
            Album(name='Rubber Soul', release_date=datetime.date(1965, 12, 3))
        ])

        beatles_json = beatles.to_json()
        self.assertTrue("John Lennon" in beatles_json)
        self.assertTrue("1965-12-03" in beatles_json)
        unpacked_beatles = Band.from_json(beatles_json)
        self.assertEqual(datetime.date(1965, 12, 3), unpacked_beatles.albums.all()[0].release_date)

    def test_deserialize(self):
        beatles = Band.from_serializable_data({
            'pk': 9,
            'albums': [],
            'name': 'The Beatles',
            'members': [
                {'pk': None, 'name': 'John Lennon', 'band': None},
                {'pk': None, 'name': 'Paul McCartney', 'band': None},
            ]
        })
        self.assertEqual(9, beatles.id)
        self.assertEqual('The Beatles', beatles.name)
        self.assertEqual(2, beatles.members.count())
        self.assertEqual(BandMember, beatles.members.all()[0].__class__)

    def test_deserialize_json(self):
        beatles = Band.from_json('{"pk": 9, "albums": [], "albums": [], "name": "The Beatles", "members": [{"pk": null, "name": "John Lennon", "band": null}, {"pk": null, "name": "Paul McCartney", "band": null}]}')
        self.assertEqual(9, beatles.id)
        self.assertEqual('The Beatles', beatles.name)
        self.assertEqual(2, beatles.members.count())
        self.assertEqual(BandMember, beatles.members.all()[0].__class__)

    def test_deserialize_with_multi_table_inheritance(self):
        fatduck = Restaurant.from_json('{"pk": 42, "name": "The Fat Duck", "serves_hot_dogs": false}')
        self.assertEqual(42, fatduck.id)

        data = fatduck.serializable_data()
        self.assertEqual(42, data['pk'])
        self.assertEqual("The Fat Duck", data['name'])

    def test_dangling_foreign_keys(self):
        heston_blumenthal = Chef.objects.create(name="Heston Blumenthal")
        snail_ice_cream = Dish.objects.create(name="Snail ice cream")
        chateauneuf = Wine.objects.create(name="Chateauneuf-du-Pape 1979")
        fat_duck = Restaurant(name="The Fat Duck", proprietor=heston_blumenthal, serves_hot_dogs=False, menu_items=[
            MenuItem(dish=snail_ice_cream, price='20.00', recommended_wine=chateauneuf)
        ])
        fat_duck_json = fat_duck.to_json()

        fat_duck = Restaurant.from_json(fat_duck_json)
        self.assertEqual("Heston Blumenthal", fat_duck.proprietor.name)
        self.assertEqual("Chateauneuf-du-Pape 1979", fat_duck.menu_items.all()[0].recommended_wine.name)

        heston_blumenthal.delete()
        fat_duck = Restaurant.from_json(fat_duck_json)
        # the deserialised record should recognise that the heston_blumenthal record is now missing
        self.assertEqual(None, fat_duck.proprietor)
        self.assertEqual("Chateauneuf-du-Pape 1979", fat_duck.menu_items.all()[0].recommended_wine.name)

        chateauneuf.delete()  # oh dear, looks like we just drank the last bottle
        fat_duck = Restaurant.from_json(fat_duck_json)
        # the deserialised record should now have a null recommended_wine field
        self.assertEqual(None, fat_duck.menu_items.all()[0].recommended_wine)

        snail_ice_cream.delete()  # NOM NOM NOM
        fat_duck = Restaurant.from_json(fat_duck_json)
        # the menu item should now be dropped entirely (because the foreign key to Dish has on_delete=CASCADE)
        self.assertEqual(0, fat_duck.menu_items.count())

    def test_deserialize_with_sort_order(self):
        beatles = Band.from_json('{"pk": null, "albums": [{"pk": null, "name": "With The Beatles", "sort_order": 2}, {"pk": null, "name": "Please Please Me", "sort_order": 1}], "name": "The Beatles", "members": []}')
        self.assertEqual(2, beatles.albums.count())

        # Make sure the albums were ordered correctly
        self.assertEqual("Please Please Me", beatles.albums.all()[0].name)
        self.assertEqual("With The Beatles", beatles.albums.all()[1].name)

    def test_deserialize_with_reversed_sort_order(self):
        Album._meta.ordering = ['-sort_order']
        beatles = Band.from_json('{"pk": null, "albums": [{"pk": null, "name": "Please Please Me", "sort_order": 1}, {"pk": null, "name": "With The Beatles", "sort_order": 2}], "name": "The Beatles", "members": []}')
        Album._meta.ordering = ['sort_order']
        self.assertEqual(2, beatles.albums.count())

        # Make sure the albums were ordered correctly
        self.assertEqual("With The Beatles", beatles.albums.all()[0].name)
        self.assertEqual("Please Please Me", beatles.albums.all()[1].name)

    def test_deserialize_with_multiple_sort_order(self):
        Album._meta.ordering = ['sort_order', 'name']
        beatles = Band.from_json('{"pk": null, "albums": [{"pk": 1, "name": "With The Beatles", "sort_order": 1}, {"pk": 2, "name": "Please Please Me", "sort_order": 1}, {"pk": 3, "name": "Please Please Me", "sort_order": 2}], "name": "The Beatles", "members": []}')
        Album._meta.ordering = ['sort_order']
        self.assertEqual(3, beatles.albums.count())

        # Make sure the albums were ordered correctly
        self.assertEqual(2, beatles.albums.all()[0].pk)
        self.assertEqual(1, beatles.albums.all()[1].pk)
        self.assertEqual(3, beatles.albums.all()[2].pk)


    WAGTAIL_05_RELEASE_DATETIME = datetime.datetime(2014, 8, 1, 11, 1, 42)

    def test_serialise_with_datetime(self):
        """
        This tests that datetimes are saved with timezone information
        """
        # Time is in America/Chicago time
        log = Log(time=self.WAGTAIL_05_RELEASE_DATETIME, data="Wagtail 0.5 released")
        log_json = json.loads(log.to_json())

        # Now check that the time is stored correctly with the timezone information at the end
        self.assertEqual(log_json['time'], '2014-08-01T11:01:42-05:00')

    def test_deserialise_with_utc_datetime(self):
        """
        This tests that a datetime with a different timezone is converted correctly
        """
        # Time is in BST
        log = Log.from_json('{"data": "Wagtail 0.5 released", "time": "2014-08-01T15:01:42-01:00", "pk": null}')

        # Naive and aware timezones cannot be compared so make the release date timezone-aware before comparison
        self.assertEqual(log.time, timezone.make_aware(self.WAGTAIL_05_RELEASE_DATETIME, timezone.get_default_timezone()))

    def test_deserialise_with_local_datetime(self):
        """
        This tests that a datetime with out timezone information is treated correctly
        """
        log = Log.from_json('{"data": "Wagtail 0.5 released", "time": "2014-08-01T11:01:42", "pk": null}')

        self.assertEqual(log.time, self.WAGTAIL_05_RELEASE_DATETIME)
