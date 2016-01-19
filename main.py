# coding=UTF-8
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.dropdown import DropDown
from kivy.properties import StringProperty, ListProperty, ObjectProperty
import soco
from threading import Thread
from Queue import Queue, Empty
from time import sleep
from functools import partial


class Controller(BoxLayout):

    currentplayer = ObjectProperty()
    players = ListProperty()
    playername = StringProperty()
    playerstatus = StringProperty()
    currenttrack = StringProperty()
    albumart = ObjectProperty()

    def __init__(self, **kwargs):
        BoxLayout.__init__(self, **kwargs)
        self.rendering = None
        self.info = None
        self.queue = Queue()
        self.activeslider = False
        Clock.schedule_interval(self.monitor, 0)
        self.thread = Thread(target=self.prepare_players)
        self.thread.daemon = True
        self.thread.start()
        self.dropdown = DropDown()

    def prepare_players(self):
        while True:
            player = soco.discovery.any_soco()
            if player:
                self.players = sorted([(x.coordinator, x.label)
                                       for x in player.all_groups])
            sleep(2.0)

    def on_players(self, instance, value):
        self.ids.players.clear_widgets()

        for p in value:
            self.ids.players.add_widget(Player(*p))

    def on_currentplayer(self, instance, value):
        if self.rendering:
            self.rendering.unsubscribe()
        if self.info:
            self.info.unsubscribe()
        self.ids.playButton.disabled = False
        self.ids.groupButton.disabled = False
        self.ids.playAntenne.disabled = False
        self.rendering = self.currentplayer.renderingControl.subscribe(
            event_queue=self.queue)
        self.info = self.currentplayer.avTransport.subscribe(
            event_queue=self.queue)

    def volumechanged(self, instance, value):
        try:
            if self.activeslider:
                self.currentplayer.volume = int(value)
        except:
            pass

    def play(self):
        if (self.playerstatus == "PLAYING"):
            self.currentplayer.pause()
        else:
            self.currentplayer.play()

    def playantenne(self):
        self.currentplayer.play_uri(uri="x-sonosapi-stream:s15547?sid=254&flags=32",
                                    title="Antenne")

    def parserenderingevent(self, event):
        if event.variables.get('output_fixed'):
            if event.output_fixed == "1":
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

    def parseavevent(self, event):
        metadata = event.current_track_meta_data

        # This can happen if the the player becomes part of a group
        if metadata == "" and event.enqueued_transport_uri_meta_data == "":
            return

        playerstate = event.transport_state
        if playerstate == "TRANSITIONING":
            return

        self.playerstatus = playerstate
        self.albumart = "http://%s:1400%s#.jpg" % (
            self.currentplayer.ip_address,
            metadata.album_art_uri)

        # Is this a radio track
        if type(event.current_track_meta_data) is soco.data_structures.DidlItem:
            currenttrack = event.enqueued_transport_uri_meta_data.title
        else:
            currenttrack = "%s - %s\n%s" % (metadata.creator,
                                            metadata.title,
                                            metadata.album)
        self.currenttrack = currenttrack

    def monitor(self, dt):
        try:
            event = self.queue.get_nowait()
        except Empty:
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
        for player in sorted(self.currentplayer.all_zones):
            btn = ToggleButton(text='%s' % (player.player_name,),
                               size_hint_y=None, height=60)
            btn.bind(on_release=partial(self.makegroup, player))
            if player in self.currentplayer.group.members:
                btn.state = "down"
            self.dropdown.add_widget(btn)
        self.dropdown.open(widget)


class Player(Button):
    name = StringProperty()

    def __init__(self, sonos, label, **kwargs):
        self.halign = "center"
        self.valign = "middle"
        self.text_size = self.size
        Button.__init__(self, **kwargs)
        self.controller = sonos
        self.text = label
        self.bind(on_press=self.setplayer)

    def setplayer(self, touch):
        self.parent.parent.currentplayer = self.controller
        self.parent.parent.playername = self.text


class SonosApp(App):

    def build(self):
        self.root = Controller()
        return self.root


SonosApp().run()
