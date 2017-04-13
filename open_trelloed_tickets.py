
import requests
import json
import time
import datetime
import argparse
import authenticate
# from ddtrace import tracer


# @tracer.wrap(service='trello-update')
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
        print "failed to get trello update timestamp with url: %s." % (url,)



# @tracer.wrap(service='trello-update')
def getTrelloTickets(view_id, auth_email, auth_pass, reverse=False):
    fr_id = '24332916'
    trello_field_ids = [24335386, 24519783, 24560146]
    order = 'asc'
    if reverse:
        order = 'desc'
    get_tickets_url = 'https://datadog.zendesk.com/api/v2/views/%s/tickets.json?sort_by=created&sort_order=%s' % (view_id, order)
    resp = json.loads(
        requests.get(url=get_tickets_url, auth=(auth_email, auth_pass)).text
    )
    # print resp
    try:
        tics = resp['tickets']
    except KeyError:
        print "no 'tickets' object in view JSON response. Probably the result of a bad API request."
        raise KeyError

    if len(tics) < 1:
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


# @tracer.wrap(service='trello-update')
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


# @tracer.wrap(service='trello-update')
def main_script():
    parser = argparse.ArgumentParser(
        description='Script to iterate through a Zendesk View to open any tickets that have trello card updates. Make sure to add the required variables to the authenticate.py before you run this.'
    )
    parser.add_argument("-v", "--view_id", type=str, required=True, help='REQUIRED: Zendesk view id nubmer. Get this from your view URL\n')
    parser.add_argument("-m", "--max", type=int, default=10, help='USEFUL: Max number of tickets to open. Default of 10. Limit of 100\n')
    parser.add_argument("-r", "--reverse", action='store_true', help='USEFUL: run through ticket view in reverse chronological order.\n')
    parser.add_argument("-e", "--email", type=str, help='OPTIONAL: Override for email of zendesk user\n')
    parser.add_argument("-p", "--password", type=str, help='OPTIONAL: Override for password of zendesk user\n')
    parser.add_argument("-t", "--trello_token", type=str, help='OPTIONAL: Override for trello authentication token\n')
    parser.add_argument("-a", "--trello_api_key", type=str, help='OPTIONAL: Override for trello api key\n')
    parser.add_argument("--verbose", action='store_true', help='DEBUG: Add for extra info on what\'s happening in the script.\n')

    uargs = parser.parse_args()
    view_id = uargs.view_id
    email = uargs.email or authenticate.zendesk_email
    password = uargs.password or authenticate.zendesk_password
    t_api = uargs.trello_api_key or authenticate.trello_api_key
    t_tok = uargs.trello_token or authenticate.trello_api_token
    v = uargs.verbose
    r = uargs.reverse or False

    trello_tics = getTrelloTickets(view_id, email, password, r)
    if v:
        print "tickets to check: \n%s" % (trello_tics,)
    # compare times
    tickets_to_open = []
    cap = uargs.max
    cnt = 1
    for tic in trello_tics:
        added = False
        if cnt <= cap:
            for link in tic['trello_links']:
                trello_time = getLastTrelloUpdateDate(link, t_api, t_tok)
                if trello_time >= tic['ticket_updated'] and added is False:
                    if v:
                        print tic['ticket_id'], tic['ticket_updated'], trello_time
                    tickets_to_open += [tic['ticket_id']]
                    added = True
                    cnt += 1
    if v:
        print "tickets needing opening:", str(len(tickets_to_open))
        print tickets_to_open
    if len(tickets_to_open) > 0:
        confirm = openTickets(tickets_to_open, email, password)
        print confirm
    else:
        print "no tickets require opening."


main_script()
