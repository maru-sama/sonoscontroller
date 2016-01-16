# coding=UTF-8
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.properties import StringProperty, ListProperty, ObjectProperty, NumericProperty
import soco
from soco.events import event_listener
from threading import Event
from Queue import Queue, Empty


class Controller(BoxLayout):

    _stop = Event()
    currentplayer = ObjectProperty()
    players = ListProperty()
    playername = StringProperty()
    playerstatus = StringProperty()
    currenttrack = StringProperty()

    def __init__(self, **kwargs):
        BoxLayout.__init__(self, **kwargs)
        self.thread = None
        self.rendering = None
        self.info = None
        self.prepare_players()
        self.queue = Queue()
        self.activeslider = False
        Clock.schedule_interval(self.monitor,0)

    def prepare_players(self, dt=None):
        player = soco.discovery.any_soco()
        if player:
            self.players = sorted([(x.coordinator, x.label) for x in player.all_groups])

    def on_players(self, instance, value):
        self.ids.players.clear_widgets()
        for p in value:
            self.ids.players.add_widget(Player(*p))

    def on_currentplayer(self, instance, value):
        if self.rendering:
            self.rendering.unsubscribe()
        if self.info:
            self.info.unsubscribe()
        if event_listener.is_running:
            event_listener.stop()

        self.ids.playButton.disabled = False
        self.rendering = self.currentplayer.renderingControl.subscribe(event_queue=self.queue)
        self.info = self.currentplayer.avTransport.subscribe(event_queue=self.queue)

    def volumechanged(self, instance, value):
        try:
            if selfactiveslider:
                self.currentplayer.volume = int(value)
        except:
            pass

    def play(self):
        if (self.playerstatus == "PLAYING"):
            self.currentplayer.stop()
        else:
            self.currentplayer.play()

    def monitor(self, dt):
        try:
            event = self.queue.get_nowait()
        except Empty:
            return

        if event.service.service_type == "RenderingControl":

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
        else:
            playerstate = event.transport_state
            if playerstate == "TRANSITIONING":
                return

            self.playerstatus = playerstate
            currenttrack = event.current_track_meta_data.title
            if "x-sonosapi-stream" in currenttrack:
                currenttrack = event.enqueued_transport_uri_meta_data.title

            self.currenttrack = currenttrack

    def volumeslider_touch_down(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.activeslider = True
            return True

    def volumeslider_touch_up(self, instance, touch):
        if touch.grab_current is instance:
            self.activeslider = False
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
