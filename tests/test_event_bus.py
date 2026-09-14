from core.event_bus import EventBus

def test_subscribe_und_publish():
    bus = EventBus()
    empfangen = []
    
    def handler(payload):
        empfangen.append(payload)
        
    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"wert": 42})

    assert len(empfangen) == 1
    assert empfangen[0]["wert"] == 42
    
def test_unsubscribe():
    bus = EventBus()
    empfangen = []
    
    def handler(payload):
        empfangen.append(payload)
        
        bus.subscribe("test.event", handler) 
        bus.unsubscribe("test.event", handler) 
        bus.publish("test.event", {"wert": 99})
        
        assert len(empfangen) == 0  

def test_mehrere_subscriber():
    bus = EventBus()
    ergebnisse = []
    
    def handler_a(payload):
        ergebnisse.append("a")
        
    def handler_b(payload):
        ergebnisse.append("b")

    bus.subscribe("test.event", handler_a)
    bus.subscribe("test.event", handler_b)
    bus.publish("test.event", {})

    assert len(ergebnisse) == 2
    assert "a" in ergebnisse
    assert "b" in ergebnisse        

