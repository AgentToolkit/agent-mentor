from typing import Any

from ibm_agent_analytics_common.interfaces.metric import Metric, MetricScope
from pydantic import Field

from agent_analytics.core.data.relatable_element_data import RelatableElementData


class MetricData(RelatableElementData,Metric):
    """_summary_
    :param RelatableElementData: _description_
    :type RelatableElementData: _type_
    :param IMetric: _description_
    :type IMetric: _type_
    """

    scope: MetricScope | dict[str, Any] | None = Field(default=None, description="Scope information for the metric")
