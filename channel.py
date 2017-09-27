import json
import time
from collections import OrderedDict
from datetime import timedelta
from functools import partial
from typing import Any, Dict, Callable, List  # noqa: F401

import aiohttp

import bot

from lib.data import ChatCommandArgs
from lib.helper.chat import cooldown, not_feature

from ..multitwitch import library as multitwitch


@not_feature('nosrlrace')
@cooldown(timedelta(seconds=30), 'srlRace', 'moderator')
async def commandSrlRace(args: ChatCommandArgs) -> bool:
    url: str = 'http://api.speedrunslive.com/races'
    session: aiohttp. ClientSession
    response: aiohttp.ClientResponse
    async with aiohttp.ClientSession(raise_for_status=True) as session, \
            session.get(url, timeout=bot.config.httpTimeout) as response:
        loads: partial[Dict[str, Any]]
        loads = partial(json.loads, object_pairs_hook=OrderedDict)
        srlRaces: Dict[str, Any] = await response.json(loads=loads)

    hasTwitch: Callable[[Dict[str, Any], str], bool]
    hasTwitch = raceHasTwitchAccountAndValid
    validTwitch: Callable[[Dict[str, Any]], bool]
    validTwitch = entrantIsStillRacingAndHasTwitchAccount
    if ('allraces' in args.message
            and args.permissions.owner
            and args.permissions.inOwnerChannel):
        hasTwitch = allRaces
    if 'allracers' in args.message:
        validTwitch = entrantHasTwitchAccount
    if 'finished' in args.message:
        hasTwitch = raceHasTwitchAccount

    races: List[Dict[str, Any]] = [r for r in srlRaces['races']
                                   if hasTwitch(r, args.chat.channel)]
    if races:
        broadcaster: str = args.chat.channel
        race: Dict[str, Any]
        for race in races:
            raceHasBroadcaster: bool = raceHasTwitchAccount(
                race, broadcaster)
            status: str
            disqualified: int
            completed: int
            forfeited: int  # noqa: E701
            racers: str
            if race['statetext'] in ['Race Over', 'Complete']:
                status = 'Race Completed'
                disqualified = len([e for e in race['entrants'].items()
                                    if e[1]['statetext'] == 'Disqualified'])
                completed = len([e for e in race['entrants'].items()
                                 if e[1]['statetext'] == 'Finished'])
                forfeited = len([e for e in race['entrants'].items()
                                 if e[1]['statetext'] == 'Forfeit'])
                racers = f'{completed} completed, {forfeited} forfeited'
                if disqualified:
                    racers += f', {disqualified} disqualified'
            elif race['statetext'] == 'In Progress':
                seconds = int(time.time() - race['time'])
                status = str(timedelta(seconds=seconds))
                disqualified = len([e for e in race['entrants'].items()
                                    if e[1]['statetext'] == 'Disqualified'])
                completed = len([e for e in race['entrants'].items()
                                 if e[1]['statetext'] == 'Finished'])
                forfeited = len([e for e in race['entrants'].items()
                                 if e[1]['statetext'] == 'Forfeit'])
                racing = len(race['entrants']) - completed - forfeited
                racers = str(completed) + ' completed, '
                racers += str(racing) + ' racing, '
                racers += str(forfeited) + ' forfeited'
                if disqualified:
                    racers += ', ' + str(disqualified) + ' disqualified'
            elif race['statetext'] == 'Entry Open':
                status = 'Waiting for entrants'
                racers = str(len(race['entrants'])) + ' entrants'
            else:
                status = race['statetext']
                racers = 'N/A'
            racerStatus: str = ''
            if raceHasBroadcaster:
                entrant: Dict[str, Any]
                entrant = [race['entrants'][u]
                           for u in race['entrants']
                           if getBroadcasterEntrant(race, u, broadcaster)][0]
                if entrant['statetext'] == 'Forfeit':
                    racerStatus = f'{broadcaster} has forfeited the race'
                elif entrant['statetext'] == 'Finished':
                    racerStatus = f'''\
{broadcaster} has finished the race in {formatOrdinal(entrant['place'])} \
place with time {formatSeconds(entrant['time'])}'''

            twitchRacers: List[str]
            twitchRacers = [race['entrants'][u]['twitch'].lower()
                            for u in race['entrants']
                            if validTwitch(race['entrants'][u])]
            if 'allracers' not in args.message:
                if broadcaster in twitchRacers and len(twitchRacers) > 16:
                    twitchRacers.remove(broadcaster)
                    twitchRacers = [broadcaster] + twitchRacers
                twitchRacers = twitchRacers[:16]

            args.chat.send(f'''\
Game: {race['game']['name']} - Goal {race['goal']} - Status: {status} - \
Racers {racers}''')
            if racerStatus:
                args.chat.send(racerStatus)
            if len(twitchRacers):
                multi = set(multitwitch.raceUrls.keys()) & set(args.message)
                if multi:
                    r = multi.pop()
                else:
                    r = multitwitch.default
                url = multitwitch.raceUrls[r](twitchRacers, race['id'])
                args.chat.send(url)
    else:
        args.chat.send(f'{args.chat.channel} is currently not in any SRL race')
    return True


def formatSeconds(seconds: int) -> str:
    return str(timedelta(seconds=seconds))


def formatOrdinal(number: int) -> str:
    index: int = (number / 10 % 10 != 1) * (number % 10 < 4) * number % 10
    suffix: str = 'tsnrhtdd'[index::4]
    return f'{number}{suffix}'


def getBroadcasterEntrant(race: Dict[str, Any], user: str, channel: str
                          ) -> bool:
    return race['entrants'][user]['twitch'].lower() == channel


def raceHasTwitchAccountAndValid(race: Dict[str, Any], channel: str) -> bool:
    raceActive = race['statetext'] not in ['Complete', 'Race Over']
    return (raceActive
            and any(map(lambda u: u['twitch'].lower() == channel,
                        race['entrants'].values())))


def raceHasTwitchAccount(race: Dict[str, Any], channel: str) -> bool:
    return any(map(lambda u: u['twitch'].lower() == channel,
                   race['entrants'].values()))


def allRaces(race: Dict[str, Any], channel: str) -> bool:
    return True


def entrantIsStillRacingAndHasTwitchAccount(entrant: Dict[str, Any]) -> bool:
    return entrant['twitch'] and entrant['statetext'] in ['Ready', 'Entered']


def entrantHasTwitchAccount(entrant: Dict[str, Any]) -> bool:
    return entrant['twitch']


'''
@not_feature('nosrlrace')
@cooldown(timedelta(seconds=30), 'srlWr', 'moderator')
async def commandSrlWr(args):
    conn = http.client.HTTPConnection('api.speedrunslive.com')

    conn.request('GET', '/races')
    response = conn.getresponse()
    responseData = response.read()

    hasTwitch = raceHasTwitchAccountAndValid
    validTwitch = entrantIsStillRacingAndHasTwitchAccount
    if ('allraces' in args.message
            and args.permissions.owner
            and args.permissions.inOwnerChannel):
        hasTwitch = allRaces
    if 'finished' in args.message:
        hasTwitch = raceHasTwitchAccount

    srlRaces = json.loads(responseData.decode('utf-8'),
                          object_pairs_hook=OrderedDict)
    races = [r for r in srlRaces['races']
             if hasTwitch(r, args.chat.channel)]
    if races:
        data = {}
        for race in races:
            if race['game']['abbrev'] not in data:
                conn.request('GET', '/goals/' + race['game']['abbrev'])
                response = conn.getresponse()
                responseData = response.read()
                srlRaces = json.loads(
                    responseData.decode('utf-8'),
                    object_pairs_hook=OrderedDict)
            goalData = data[race['game']['abbrev']]
            args.chat.send(
                'Game: ' + race['game']['name'] +
                ' - Goal: ' + race['goal'] +
                ' - Status: ' + status +
                ' - Racers: ' + racers)
            if racerStatus:
                args.chat.send(racerStatus)
            if len(twitchRacers):
                if 'kadgar' in args.message:
                    args.chat.send('http://kadgar.net/live/'
                                   + '/'.join(twitchRacers))
                elif 'speedruntv' in args.message:
                    url = 'http://speedrun.tv/race:' + race['id'] + '/'
                    url += '/'.join(twitchRacers)
                    args.chat.send(url)
                elif 'kbmod' in args.message:
                    url = 'http://kbmod.com/multistream/'
                    url += '/'.join(twitchRacers)
                    args.chat.send(url)
                else:
                    args.chat.send('http://multitwitch.tv/'
                                   + '/'.join(twitchRacers))
    else:
        args.chat.send(args.chat.channel + ' is currently not in any SRL race')
    conn.close()
'''
