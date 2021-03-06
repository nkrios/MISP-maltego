from canari.maltego.transform import Transform
# from canari.framework import EnableDebugWindow
from MISP_maltego.transforms.common.entities import MISPEvent, MISPGalaxy
from MISP_maltego.transforms.common.util import get_misp_connection, galaxycluster_to_entity, get_galaxy_cluster, get_galaxies_relating, search_galaxy_cluster, mapping_galaxy_icon
from canari.maltego.message import UIMessageType, UIMessage, LinkDirection


__author__ = 'Christophe Vandeplas'
__copyright__ = 'Copyright 2018, MISP_maltego Project'
__credits__ = []

__license__ = 'AGPLv3'
__version__ = '0.1'
__maintainer__ = 'Christophe Vandeplas'
__email__ = 'christophe@vandeplas.com'
__status__ = 'Development'


# @EnableDebugWindow
class GalaxyToEvents(Transform):
    """Expands a Galaxy to multiple MISP Events."""

    # The transform input entity type.
    input_type = MISPGalaxy

    def do_transform(self, request, response, config):
        maltego_misp_galaxy = request.entity
        misp = get_misp_connection(config)
        if maltego_misp_galaxy.tag_name:
            tag_name = maltego_misp_galaxy.tag_name
        else:
            tag_name = maltego_misp_galaxy.value
        events_json = misp.search(controller='events', tags=tag_name, withAttachments=False)
        for e in events_json['response']:
            response += MISPEvent(e['Event']['id'], uuid=e['Event']['uuid'], info=e['Event']['info'], link_direction=LinkDirection.OutputToInput)
        return response


# @EnableDebugWindow
class GalaxyToRelations(Transform):
    """Expans a Galaxy to related Galaxies and Clusters"""
    input_type = MISPGalaxy

    def do_transform(self, request, response, config):
        maltego_misp_galaxy = request.entity

        if maltego_misp_galaxy.uuid:
            current_cluster = get_galaxy_cluster(uuid=maltego_misp_galaxy.uuid)
        elif maltego_misp_galaxy.tag_name:
            current_cluster = get_galaxy_cluster(tag=maltego_misp_galaxy.tag_name)
        elif maltego_misp_galaxy.name:
            current_cluster = get_galaxy_cluster(tag=maltego_misp_galaxy.name)

        if not current_cluster:
            # maybe the user is searching for a cluster based on a substring.
            # Search in the list for those that match and return galaxy entities
            potential_clusters = search_galaxy_cluster(maltego_misp_galaxy.name)
            # TODO check if duplicates are possible
            if potential_clusters:
                for potential_cluster in potential_clusters:
                    response += galaxycluster_to_entity(potential_cluster, link_label='Search result')
                return response

        if not current_cluster:
            response += UIMessage("Galaxy Cluster UUID not in local mapping. Please update local cache; non-public UUID are not supported yet.", type=UIMessageType.Inform)
            return response
        c = current_cluster
        # update existing object

        galaxy_cluster = get_galaxy_cluster(c['uuid'])
        icon_url = None
        if 'icon' in galaxy_cluster:  # map the 'icon' name from the cluster to the icon filename of the intelligence-icons repository
            try:
                icon_url = mapping_galaxy_icon[galaxy_cluster['icon']]
            except Exception:
                # it's not in our mapping, just ignore and leave the default Galaxy icon
                pass
        if c['meta'].get('synonyms'):
            synonyms = ', '.join(c['meta']['synonyms'])
        else:
            synonyms = ''
        request.entity.name = '{}\n{}'.format(c['type'], c['value'])
        request.entity.uuid = c['uuid']
        request.entity.description = c.get('description')
        request.entity.cluster_type = c.get('type')
        request.entity.cluster_value = c.get('value')
        request.entity.synonyms = synonyms
        request.entity.tag_name = c['tag_name']
        request.entity.icon_url = icon_url
        # response += request.entity
        # find related objects
        if 'related' in current_cluster:
            for related in current_cluster['related']:
                related_cluster = get_galaxy_cluster(related['dest-uuid'])
                if related_cluster:
                    response += galaxycluster_to_entity(related_cluster, link_label=related['type'])
        # find objects that are relating to this one
        for related in get_galaxies_relating(current_cluster['uuid']):
            related_link_label = ''
            for rel_in_rel in related['related']:
                if rel_in_rel['dest-uuid'] == current_cluster['uuid']:
                    related_link_label = rel_in_rel['type']
                    break
            response += galaxycluster_to_entity(related, link_label=related_link_label, link_direction=LinkDirection.OutputToInput)
        return response
