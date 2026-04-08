from django.http import HttpResponse

def prometheus_metrics_view(_request):
    from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest, multiprocess, REGISTRY
    from os import getenv

    registry = CollectorRegistry()
    
    if getenv('PROMETHEUS_MULTIPROG_DIR'):
        multiprocess.MultiProcessCollector(registry)
    else:
        if registry._collector_to_names == {}:
            registry = REGISTRY

    from .metrics import BackUpByTypeCollector, ResponseByStatusCollector, ResponseByDateCollector
    def is_collector_registered(mycollector):
        for collector in registry._collector_to_names.keys():
            if isinstance(collector, mycollector):
                return True
        return False

    if not is_collector_registered(BackUpByTypeCollector):
        registry.register(BackUpByTypeCollector())
    if not is_collector_registered(ResponseByStatusCollector):
        registry.register(ResponseByStatusCollector())
    if not is_collector_registered(ResponseByDateCollector):
        registry.register(ResponseByDateCollector())

    output = generate_latest(registry)
    return HttpResponse(output, content_type=CONTENT_TYPE_LATEST)
