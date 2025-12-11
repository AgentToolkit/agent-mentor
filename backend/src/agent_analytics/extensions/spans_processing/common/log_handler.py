from datetime import UTC, datetime

import pandas as pd

from agent_analytics.extensions.spans_processing.common.utils import load_log_content


class LogHandler:
    def __init__(self, log_json, trace_id=None, is_instana_format=True):
        self.json = log_json
        self.trace_id = trace_id
        self.graph_node_names = []
        self.preprocess(is_instana_format=is_instana_format)

    @classmethod
    def from_log_content(cls, log_content):
        return cls(load_log_content(log_content), is_instana_format=False)

    def get_df(self):
        return self.df

    def get_json(self):
        return self.json

    def deep_normalize(self, json_data):
        # currently reverted to simple normalization - following the JSON preprocessing
        final_df = pd.json_normalize(
            data=json_data,
        )

        return final_df

    def preprocess(self, is_instana_format=False):
        json_data = []
        if is_instana_format:
            for trace in self.json:
                divide_by = 1
                if trace['timestamp'] > 10000000000: # time in millis
                    divide_by = 1000

                trace['start_time'] = datetime.fromtimestamp(trace['timestamp'] / divide_by, tz=UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                trace['end_time'] = datetime.fromtimestamp((trace['timestamp'] + trace['duration']) / divide_by, tz=UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                trace['context'] = {
                    'span_id': trace['spanId'],
                    'trace_id': self.trace_id # should be filled for instana traces
                }

                trace['parent_id'] = trace['parentSpanId']
                trace['name'] = trace['label']

                if 'data' in trace and \
                    'tags' in trace['data']:
                    trace['attributes'] = trace['data']['tags']
                    json_data.append(trace)

                    if 'traceloop.association.properties.langgraph_node' in trace['attributes']:
                        node_name = trace['attributes']['traceloop.association.properties.langgraph_node']
                        if node_name != "__start__" and node_name not in self.graph_node_names:
                            self.graph_node_names.append(node_name)

            self.json = json_data
            self.df = self.deep_normalize(self.json) # pd.json_normalize(self.json)
        else:
            for trace in self.json:
                if 'traceloop.association.properties.langgraph_node' in trace['attributes']:
                    node_name = trace['attributes']['traceloop.association.properties.langgraph_node']
                    if node_name != "__start__" and node_name not in self.graph_node_names:
                        self.graph_node_names.append(node_name)


            self.df = pd.json_normalize(self.json)

        self.df.sort_values(by=['start_time', 'end_time'], inplace=True)
