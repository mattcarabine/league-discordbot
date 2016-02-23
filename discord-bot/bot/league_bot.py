from collections import defaultdict, OrderedDict
import os
import logging
from riotwatcher import RiotWatcher, EUROPE_WEST, LoLException, error_404

from discord_bot import DiscordBot
from manager.manager import CouchbaseManager, FileNotFoundError, FileManager
from util.import_champs import import_champs

league_bot_logger = logging.getLogger('discordbot.leaguebot')
league_bot_logger.level = logging.INFO

WANTED_SUB_TYPES = ['NORMAL', 'RANKED_SOLO_5x5', 'RANKED_TEAM_5x5',
                    'CAP_5x5']

class LeagueBot(DiscordBot):

    def __init__(self, client):
        super(LeagueBot, self).__init__(client, 'leaguebot')
        self.storage_manager = CouchbaseManager(
            os.environ.get('MATCH_HISTORY_BUCKET'))
        self.riot = RiotWatcher(os.environ.get('RIOT_API_KEY'),
                                default_region=EUROPE_WEST)
        self.players = self.load_player_list()
        self.champions = self.load_champions()

    def load_player_list(self):
        try:
            players = self.storage_manager.get('players')
        except FileNotFoundError:
            players = {}

        return players

    def load_champions(self):
        try:
            champs = self.storage_manager.get('champions')
        except FileNotFoundError:
            champs = import_champs()
            self.storage_manager.set('champions', champs)

        return champs

    @DiscordBot.add_command('add')
    def add_player(self, *args):
        player = ''.join(args)
        if player.lower() not in self.players:
            try:
                summoner = self.riot.get_summoner(name=player)
            except LoLException as e:
                if e == error_404:
                    self.send_message('Error - Player {} does not exist'
                                      .format(player))
                else:
                    self.send_message('An unknown error occurred, let Matt know!')
                    league_bot_logger.warning(e)
                return
            self.players[summoner['name'].lower()] = summoner['id']
            self.send_message('Added {} to list of players'.format(player))
            self.storage_manager.set('players', self.players)
        else:
            self.send_message('{} already in the list of players'.format(player))

    @DiscordBot.add_command('list')
    def print_players(self, *_):
        if self.players:
            player_list = '\n'
            for player, player_id in self.players.iteritems():
                try:
                    number_of_games = len(self.storage_manager.get('matches-{}'
                                          .format(player_id))['games'])
                except FileNotFoundError:
                    number_of_games = 0

                player_list += '{} - {} games\n'.format(player,
                                                        number_of_games)

            self.send_message(player_list)
        else:
            self.send_message('Player list empty')

    @DiscordBot.add_command('current-games')
    def get_current_games(self, *_):
        for player in self.players:
            self.get_current_game(player)

    @DiscordBot.add_command('current-game')
    def get_current_game(self, *args):
        player = ''.join(args).lower()
        if player not in self.players.keys():
            try:
                summoner = self.riot.get_summoner(name=player)
            except LoLException as e:
                if e == error_404:
                    self.send_message(
                        'Error - Player {} does not exist'.format(player))
                else:
                    self.send_message(
                        'An unknown error occurred, let Matt know!')
                    league_bot_logger.warning(e)
                return
            else:
                player_id = summoner['id']
        else:
            player_id = self.players[player]

        try:
            curr_game = self.riot.get_current_game(player_id)
        except LoLException as e:
            if e == error_404:
                self.send_message('{} is not in a game'.format(player))
            else:
                league_bot_logger.warning(e)
        else:
            game_length = (int(curr_game['gameLength']) / 60) + 3
            for participant in curr_game['participants']:
                if participant['summonerName'].lower() == player.lower():
                    champion = self.champions[str(participant['championId'])]
                    lolnexus_url = (
                        'http://www.lolnexus.com/EUW/search?name={}&region=EUW'
                        .format(player))

                    self.send_message(
                        '{} has been in a game for {} minutes - Playing {}\n'
                        'Link to game: {}'
                        .format(player, game_length, champion, lolnexus_url))
                    break

    @DiscordBot.add_command('stats')
    def summarise_stats(self, *args):
        player = ''.join(args).lower()
        if player not in self.players:
            self.send_message('{} not in list of players, no stats found'.format(player))
        matches = self.storage_manager.get('matches-{}'.format(self.players[player]))
        stat_averages = defaultdict(list)
        match_counter = 0
        for match in matches['games']:
            if match['subType'] in WANTED_SUB_TYPES:
                match_counter += 1
                for stat, value in match['stats'].iteritems():
                    stat_averages[stat].append(value)

        output = ''
        for stat, value in OrderedDict(sorted(stat_averages.items())).iteritems():
            try:
                output += '{} - {:.3f}\n'.format(stat, float(sum(value)) / match_counter)
            except TypeError:
                pass
        output += 'Games - {}'.format(match_counter)
        self.send_message(output)

    @DiscordBot.add_command('is')
    def dank_meme(self, *args):
        print 'got here'
        self.send_message("It's not boosting, it's just elo rushing, he is entitled to be there")