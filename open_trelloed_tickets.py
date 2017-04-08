
import requests
import json
import time
import datetime
import argparse


def getLastTrelloUpdateDate(url, key, token):
    try:
        the_text = requests.get(
            '%s.json?fields=dateLastActivity&key=%s&token=%s' %
            (url, key, token)
        ).text
        the_json = json.loads(the_text)
        date_string = the_json['dateLastActivity']
        # print date_string
        ts = time.mktime(
            datetime.datetime.strptime(
                date_string, '%Y-%m-%dT%H:%M:%S.%fZ'
            ).timetuple()
        )
        return ts
    except Exception:
        raise "failed to get trello update timestamp, error: %s" % (Exception,)


def getTrelloTickets(view_id, auth_email, auth_pass):
    fr_id = '24332916'
    trello_field_ids = [24335386, 24519783, 24560146]
    get_tickets_url = 'https://datadog.zendesk.com/api/v2/views/%s/tickets.json?sort_by=created&sort_order=asc' % (view_id,)
    resp = json.loads(
        requests.get(url=get_tickets_url, auth=(auth_email, auth_pass)).text
    )
    # print resp
    try:
        tics = resp['tickets']
    except KeyError:
        raise "no 'tickets' object in view JSON reponse. Probably the result of a bad API request. Error: %s" % (KeyError,)

    if len(tics) > 1:
        print "no tickets in view. ending."
        exit()
    tics_with_trel_links = []
    for tic in tics:
        tic_id = tic['id']
        tic_updated = tic['updated_at']
        trello_link_list = []
        for cust in tic['custom_fields']:
            if cust['id'] == fr_id:
                fr = bool(cust['value'])  # in case we want this later
            elif cust['id'] in trello_field_ids:
                if cust['value'] and len(cust['value']) > 19:
                    if cust['value'][:19] == 'https://trello.com/':
                        trello_link_list += [cust['value']]
        if len(trello_link_list) > 0:
            # print tic_id
            tics_with_trel_links += [{
                'ticket_id': str(tic_id),
                'ticket_updated': time.mktime(
                    datetime.datetime.strptime(
                        tic_updated, '%Y-%m-%dT%H:%M:%SZ'
                    ).timetuple()
                ),
                'trello_links': trello_link_list,
            }]
    return tics_with_trel_links


def openTickets(ticket_list, auth_email, auth_pass):
    open_tickets_url = str(
        'https://datadog.zendesk.com/api/v2/tickets/update_many.json?ids=%s' %
        (','.join(ticket_list),)
    )
    parms = json.dumps({"ticket": {"status": "open"}})
    print "opening tickets: %s" % (','.join(ticket_list),)
    # print open_tickets_url
    resp = requests.put(
        url=open_tickets_url,
        auth=(auth_email, auth_pass),
        data=parms,
        headers={'content-type': 'application/json'}
    ).text
    return resp


parser = argparse.ArgumentParser(description='Script to iterate through a Zendesk View to open any tickets that have trello card updates')
parser.add_argument("-v", "--view_id", type=str, required=True, help='Zendesk view id nubmer. Get this from your view URL')
parser.add_argument("-e", "--email", type=str, required=True, help='Email of zendesk user')
parser.add_argument("-p", "--password", type=str, required=True, help='Password of zendesk user')
parser.add_argument("-m", "--max", type=str, help='max number of tickets to open. Default of 10. Limit of 100')
parser.add_argument("-t", "--trello_token", required=True, type=str, help='trello authentication token')
parser.add_argument("-a", "--trello_api_key", required=True, type=str, help='trello api key')

uargs = parser.parse_args()

trello_tics = getTrelloTickets(uargs.view_id, uargs.email, uargs.password)

# compare times
tickets_to_open = []
cap = uargs.max or 10
cnt = 1
for tic in trello_tics:
    added = False
    if cnt <= cap:
        for link in tic['trello_links']:
            trello_time = getLastTrelloUpdateDate(
                link, uargs.trello_api_key, uargs.trello_token
            )
            if trello_time >= tic['ticket_updated'] and added is False:
                # print tic['ticket_id'], tic['ticket_updated'], trello_time
                tickets_to_open += [tic['ticket_id']]
                added = True
                cnt += 1

# print "tickets needing opening:", str(len(tickets_to_open))
print tickets_to_open
if len(tickets_to_open) > 0:
    confirm = openTickets(tickets_to_open, uargs.email, uargs.password)
    print confirm
else:
    print "no tickets require opening."
