import sys
import re
import codecs
import io


class HandHistory(object):
    def __init__(self, filename):
        self.filename = filename
        self._hands = 0

    def __enter__(self):
        self.file = codecs.open(self.filename, 'r', 'utf-8')
        return self

    def __exit__(self, t, v, tb):
        if not self.file.closed:
            self.file.close()

    def hands(self):
        return self._hands

    def read_hand(self):
        text = ''
        while True:
            line = self.file.readline()
            if not line:
                return None
            if line != '\n' and line != '\r\n':
                text += line
            elif (line == '\n' or line == '\r\n') and text:
                break
        self._hands += 1
        return text


class HandError(Exception):
    def __init__(self, msg, id=''):
        self.msg = msg
        self.id = id

    def __str__(self):
        if self.id:
            return self.msg + " -> id: " + self.id
        return self.msg

    def _repr__(self):
        if self.id:
            return self.msg + " -> id: " + self.id
        return self.msg


class Network(object):
    UNKNOWN = 1
    POKERSTARS = 2


class Hand(object):
    def __init__(self, text):
        self.text = io.StringIO(text)
        self._network = None
        self.date_time_stamp = None
        self.id = None
        self.play_money = None
        self.table_name = None
        self.table_size = None
        self.game_type = None

    def _parse_network(self):
        line = self.text.getvalue().splitlines()[0]
        if line.find('PokerStars') != -1:
            self._network = Network.POKERSTARS
        else:
            self._network = Network.UNKNOWN
            raise HandError('Unknown network: ' + line)

    def network(self):
        if not self._network:
            self._parse_network()
        return self._network


class PokerStarsHand(Hand):
    def __init__(self):
        super(PokerStarsHand, self).__init__()

    def _parse_table_header(self):
        line = self.text.getvalue().splitlines()[1]
        obj = re.search(r"Table '(.*)' (.*) \((.*)\) Seat #([0-9]*) is the button", line)
        if obj:
            if obj.group(3) == 'Play Money':
                self.play_money = True
                self.table_name = obj.group(1)
                self.table_size = obj.group(2)
                self.btn = obj.group(4)
            else:
                raise HandError('Unknown play money table header: ' + line, self.id)
        else:
            raise HandError('Unable to parse table header: ' + line, self.id)

    def _parse_hand_header(self):
        line = self.text.getvalue().splitlines()[0]

        obj = re.search(r"Hold'em (.*) \(([0-9]*)/([0-9]*).*\) - (.*)", line)

        if obj:
            self.sb = str(int(obj.group(2)) * 0.00001)
            self.bb = str(int(obj.group(3)) * 0.00001)

            if obj.group(1) == 'No Limit':
                self.game_type = 'No Limit'
            elif obj.group(1) == 'Pot Limit':
                self.game_type = 'Pot Limit'
            elif obj.group(1) == 'Fixed Limit':
                self.game_type = 'Fixed Limit'
            else:
                raise HandError('Game type not recognised: ' + line, self.id)

            self.date_time_stamp = obj.group(4)
        else:
            raise HandError('Unable to parse blind amounts: ' + line, self.id)

    def _parse_id(self):
        line = self.text.getvalue().splitlines()[0]
        obj = re.search(r"Hand #([0-9]*):", line)

        if obj:
            self.id = obj.group(1)
        else:
            raise HandError('Unable to parse hand id: ' + line)

    def parse(self):
        self._parse_id()
        self._parse_table_header()
        self._parse_hand_header()

    def _convert(self, regex, line):
        obj = re.search(regex, line)
        if obj:
            for index in range(1, len(obj.groups()) + 1):
                if obj.group(index).isdigit():
                    amount = (int(obj.group(index)) * 0.00001)
                    line = re.sub(obj.group(index), "${:.2f}".format(amount).replace('.00', ''), line)
        return line

    def print(self):
        print('PokerStars Hand #' + self.id + ':  Hold\'em ' + self.game_type + ' ($' + self.sb +
              '/$' + self.bb + ' USD) - ' + self.date_time_stamp)
        print('Table \'' + self.table_name + '\' ' + self.table_size + ' Seat #' + self.btn + ' is the button')
        lines = 0
        for line in self.text:
            if lines < 2:
                lines += 1
            else:
                line = self._convert(r"\(([0-9]*) in chips\)", line)
                line = self._convert(r"posts (.*) blind ([0-9]*)", line)
                line = self._convert(r": bets ([0-9]*)", line)
                line = self._convert(r": calls ([0-9]*)", line)
                line = self._convert(r": raises ([0-9]*) to ([0-9]*)", line)
                line = self._convert(r" collected ([0-9]*) from pot", line)
                line = self._convert(r" collected \(([0-9]*)\)", line)
                line = self._convert(r"Total pot ([0-9]*) \| Rake ([0-9]*)", line)
                line = self._convert(r"and won \(([0-9]*)\) with", line)
                line = self._convert(r"Uncalled bet \(([0-9]*)\) returned to", line)
                line = self._convert(r"posts small & big blinds ([0-9]*)", line)
                print(line.strip())
        print('\n\n')


def main():
    try:
        if len(sys.argv) < 2:
            sys.stderr.write('{} <filename>\n'.format(sys.argv[0]))
            return
        with HandHistory(sys.argv[1]) as history:
            errors = 0
            while True:
                try:
                    text = history.read_hand()
                    if not text:
                        break
                    hand = Hand(text)
                    if hand.network() == Network.POKERSTARS:
                        hand.__class__ = PokerStarsHand
                    hand.parse()
                    hand.print()
                except HandError as e:
                    errors += 1
                    sys.stderr.write(str(e) + '\n')
            sys.stderr.write('{} hands, {} errors\n'.format(history.hands(), errors))
    except (IOError, OSError) as e:
        sys.stderr.write(str(e) + '\n')
    finally:
        pass


if __name__ == '__main__':
    main()
