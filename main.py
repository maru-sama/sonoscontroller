# coding=UTF-8
from kivy.app import App
from kivy.clock import mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.dropdown import DropDown
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty, ObjectProperty
import soco
from threading import Thread
from time import sleep
from functools import partial

try:
    from Queue import Queue
except ImportError:
    from queue import Queue


class Placeholder(Label):
    def teardown(self):
        pass


class CurrentPlayer(BoxLayout):
    players = ListProperty()
    playername = StringProperty()
    playerstatus = StringProperty()
    currenttrack = StringProperty()
    albumart = ObjectProperty()

    def __init__(self, player, **kwargs):
        BoxLayout.__init__(self, **kwargs)
        self.queue = Queue()
        self.activeslider = False
        self.dropdown = DropDown()
        self.stationdropdown = DropDown()
        self.currentplayer = player
        self.playerstatus = "Pending ...."
        self.playername = self.currentplayer.group.label
        self.swipe = 0
        self.rendering = self.currentplayer.renderingControl.subscribe(
            auto_renew=True, event_queue=self.queue)
        self.info = self.currentplayer.avTransport.subscribe(
            auto_renew=True, event_queue=self.queue)
        self.thread = Thread(target=self.monitor)
        self.thread.daemon = True
        self.thread.start()

    def teardown(self):

        self.queue.put(None)
        if self.rendering:
            try:
                self.rendering.unsubscribe()
            except:
                pass
        if self.info:
            try:
                self.info.unsubscribe()
            except:
                pass

    def volumechanged(self, instance, value):
        try:
            if self.activeslider:
                for p in self.currentplayer.group.members:
                    p.volume = int(value)
        except:
            pass

    def play(self):
        if (self.playerstatus == "PLAYING"):
            self.currentplayer.pause()
        else:
            try:
                self.currentplayer.play()
            except:
                pass

    def radiostations(self, widget):
        self.stationdropdown.clear_widgets()
        for station in self.currentplayer.get_favorite_radio_stations()['favorites']: # noqa
            btn = Button(text='%s' % (station['title'],),
                         size_hint_y=None, height=60,
                         halign="center", valign="middle")
            btn.bind(size=btn.setter("text_size"))
            btn.bind(on_release=partial(self.playradio, station))
            self.stationdropdown.add_widget(btn)
        self.stationdropdown.open(widget)

    def playradio(self, station, widget):
        self.currentplayer.play_uri(uri=station['uri'], #noqa
                                    title="Radio")
        self.stationdropdown.select(station['title'])

    @mainthread
    def parserenderingevent(self, event):
        if event.variables.get('output_fixed') == 1:
            self.ids.playervolume.disabled = True
            self.ids.playervolume.value = 100
            return
        else:
            self.ids.playervolume.disabled = False

        if not self.activeslider:
            try:
                self.ids.playervolume.value = int(event.volume['Master'])
            except:
                pass

    @mainthread
    def parseavevent(self, event):
        playerstate = event.transport_state
        if playerstate == "TRANSITIONING":
            return

        self.playerstatus = playerstate
        try:
            metadata = event.current_track_meta_data
        except:
            return

        # This can happen if the the player becomes part of a group
        if metadata == "" or not hasattr(metadata, "album_art_uri"):
            return
        if metadata.album_art_uri.startswith("http"):
            albumart = metadata.album_art_uri
        else:
            albumart = "http://%s:1400%s#.jpg" % (
                self.currentplayer.ip_address,
                metadata.album_art_uri)
        #self.update_albumart(albumart)
        self.albumart = albumart

        # Is this a radio track
        if type(metadata) is soco.data_structures.DidlItem:
            currenttrack = metadata.stream_content
        else:
            if hasattr(metadata, 'album'):
                album = metadata.album
            elif hasattr(event, "enqueued_transport_uri_meta_data") and \
                    hasattr(event.enqueued_transport_uri_meta_data, 'title'):
                album = event.enqueued_transport_uri_meta_data.title
            else:
                album = ""
            currenttrack = "%s - %s\n%s" % (metadata.creator,
                                            metadata.title,
                                            album)
        self.currenttrack = currenttrack

    def monitor(self):
        while True:
            event = self.queue.get()
            if event is None:
                return

            if event.service.service_type == "RenderingControl":
                self.parserenderingevent(event)
            else:
                self.parseavevent(event)

    def volumeslider_touch_down(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.activeslider = True
            return True

    def volumeslider_touch_up(self, instance, touch):
        if touch.grab_current is instance:
            self.activeslider = False
            return True

    def makegroup(self, player, widget):
        if player in self.currentplayer.group.members:
            player.unjoin()
        else:
            player.join(self.currentplayer)

    def editgroup(self, widget):
        self.dropdown.clear_widgets()
        for player in sorted(self.currentplayer.all_zones,
                             key=lambda x: x.player_name):
            btn = ToggleButton(text='%s' % (player.player_name,),
                               size_hint_y=None, height=60)
            btn.bind(on_release=partial(self.makegroup, player))
            if player in self.currentplayer.group.members:
                btn.state = "down"
            self.dropdown.add_widget(btn)
        self.dropdown.open(widget)

    def updatename(self):
        self.playername = self.currentplayer.group.label

    def swipe_start(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.swipe = touch.x
            touch.grab(self)
            return True

    def swipe_stop(self, instance, touch):
        if touch.grab_current is self:
            try:
                if touch.x > self.swipe:
                    self.currentplayer.previous()
                elif touch.x < self.swipe:
                    self.currentplayer.next()
            except:
                pass
            return True


class Controller(BoxLayout):
    player = ObjectProperty(None)
    players = ListProperty()

    def __init__(self, **kwargs):
        BoxLayout.__init__(self, **kwargs)
        self.thread = Thread(target=self.prepare_players)
        self.thread.daemon = True
        self.thread.start()
        self.player = Placeholder()
        self.add_widget(self.player)

    def prepare_players(self):
        while True:
            try:
                player = soco.discovery.any_soco()
                if player:
                    players = [x.coordinator for x in
                                    sorted(player.all_groups,
                                           key=lambda x: x.label)]
                    self.update_players(players)
            except:
                pass
            sleep(2.0)

    @mainthread
    def update_players(self, players):
       self.players = players

    def on_players(self, instance, value):
        if isinstance(self.player, CurrentPlayer):
            if self.player.currentplayer not in value:
                self.player.teardown()
                self.remove_widget(self.player)
                self.player = Placeholder()
                self.add_widget(self.player)
            else:
                self.player.updatename()

        self.ids.players.clear_widgets()
        for p in value:
            self.ids.players.add_widget(Player(p))

    def setplayer(self, player):
        if self.player:
            self.player.teardown()
            self.remove_widget(self.player)
        self.player = CurrentPlayer(player)
        self.add_widget(self.player)


class Player(Button):

    def __init__(self, sonos, **kwargs):
        Button.__init__(self, **kwargs)
        self.controller = sonos
        self.text = sonos.group.label

    def on_press(self):
        self.parent.parent.setplayer(self.controller)


class SonosApp(App):

    def build(self):
        self.root = Controller()
        return self.root


SonosApp().run()
