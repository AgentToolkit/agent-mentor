
from agent_analytics_common.interfaces.recommendations import Recommendation

from agent_analytics.core.data.relatable_element_data import RelatableElementData


class RecommendationData(RelatableElementData, Recommendation):
    """
    Data object for Recommendation with related elements support.
    
    :param RelatableElementData: Base data class for relatable elements
    :type RelatableElementData: class
    :param Recommendation: Recommendation interface
    :type Recommendation: class
    """
    pass
