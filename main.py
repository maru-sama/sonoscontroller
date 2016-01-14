# coding=UTF-8
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.properties import StringProperty, ListProperty, ObjectProperty, NumericProperty
import soco
from threading import Thread, Event
from Queue import Queue, Empty


class Controller(BoxLayout):

    _stop = Event()
    currentplayer = ObjectProperty()
    players = ListProperty()
    playername = StringProperty()
    playerstatus = StringProperty()
    currenttrack = StringProperty()
    playervolume = NumericProperty()
    activeslider = NumericProperty(0)

    def __init__(self, **kwargs):
        BoxLayout.__init__(self, **kwargs)
        self.thread = None
        self.prepare_players()
        Clock.schedule_interval(self.prepare_players,2)

    def prepare_players(self, dt=None):
        player = soco.discovery.any_soco()
        if player:
            self.players = sorted([(x.coordinator, x.label) for x in player.all_groups])

    def on_players(self, instance, value):
        if self.thread:
            self._stop.set()
            self.thread.join()
            self._stop.clear()
        self.ids.players.clear_widgets()
        for p in value:
            print p
            self.ids.players.add_widget(Player(*p))

    def on_currentplayer(self, instance, value):
        self.ids.playButton.disabled = False
        self.ids.PlayerVolume.disabled = False
        if self.thread:
            self._stop.set()
            self.thread.join()
            self._stop.clear()

        self.thread = Thread(target=self.monitor)
        self.thread.start()

    def volumechanged(self, instance, value):
        try:
            if self.activeslider:
                self.currentplayer.volume = int(value)
        except:
            pass

    def play(self):
        if (self.playerstatus == "PLAYING"):
            self.currentplayer.stop()
        else:
            self.currentplayer.play()

    def monitor(self):
        rendering = self.currentplayer.renderingControl.subscribe()
        info = self.currentplayer.avTransport.subscribe()

        while not self._stop.isSet():
            try:
                event = rendering.events.get(timeout=0.4)
                if not self.activeslider:
                    try:
                        self.playervolume = int(event.variables['volume']['Master'])
                    except:
                        pass
            except Empty:
                pass

            try:
                event = info.events.get(timeout=0.1)
                playerstate = event.variables['transport_state']
                if playerstate == "TRANSITIONING":
                    continue

                self.playerstatus = playerstate
                try:
                    self.currenttrack = event.variables['av_transport_uri_meta_data'].title
                except:
                    radiotrack = event.variables['current_track_meta_data'].title
                    if radiotrack == "x-sonosapi-stream:s15547?sid=254&flags=32":
                        radiotrack = "Antenne Kärnten"
                    self.currenttrack = radiotrack

            except Empty:
                pass

        try:
            rendering.unsubscribe()
            info.unsubscribe()
        except:
            pass

    def volumeslider_touch_down(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.activeslider = 1
            return True

    def volumeslider_touch_up(self, instance, touch):
        if touch.grab_current is instance:
            self.activeslider = 0
            return True


class Player(Button):
    name = StringProperty()

    def __init__(self, sonos, label, **kwargs):
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

    def on_stop(self):
        self.root._stop.set()

SonosApp().run()
