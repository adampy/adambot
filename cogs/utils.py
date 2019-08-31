TIMES = {'w':7*24*60*60,
         'week':7*24*60*60,
         'weeks':7*24*60*60,
         'd':24*60*60,
         'day':24*60*60,
         'days':24*60*60,
         'h':60*60,
         'hour':60*60,
         'hours':60*60,
         'hr':60*60,
         'h':60*60,
         'm':60,
         'minute':60,
         'minutes':60,
         'min':60,
         'mins':60,
         's':1,
         'second':1,
         'seconds':1,
         'sec':1,
         'secs':1}

def separate_args(args):
    '''Given the args tuple (from *args) and returns seconds in index position 0 and reason in index position 1'''
    arg_list = [arg for arg in ' '.join(args).split('-') if arg]
    seconds = 0
    reason = ''
    for item in arg_list:
        if item[0] == 't':
            time = item[1:].strip()
            times = []
            #split after the last character before whitespace after int
            temp1 = '' #time
            temp2 = '' #unit
            for i, letter in enumerate(time):
                if letter == ' ' and (temp1 and temp2):
                    times.append([temp1, temp2])
                    temp1, temp2 = '', ''
                    #print('append')
                if letter.isdigit():
                    if not temp2:
                        temp1 += letter
                        #print('add time')
                    else:
                        times.append([temp1, temp2])
                        temp1, temp2 = '', ''
                        temp1 += letter
                        #print('append')
                else:
                    if temp1 and letter != ' ':
                        temp2 += letter
                        #print('add letter')
            times.append([temp1, temp2])

            print(times)
            for sets in times:

                try:
                    time, unit = sets
                    if unit in TIMES.keys():
                        multiplier = TIMES[unit]
                        seconds += int(time)*multiplier
                except ValueError:
                    pass

            print(seconds)
            
        if item[0] == 'r':
            reason = item[1:].strip()
            print(reason)
    return seconds, reason

def old_separate_args(args):
    '''Given the args tuple (from *args) and returns timeperiod in index position 0 and reason in index position 1'''
    reason = ''
    timeperiod =''
    if args:
        arg_list = [arg for arg in ' '.join(args).split('-') if arg]
        for item in arg_list:
            if item[0] == 't':
                timeperiod = item[2:]
                if timeperiod[len(timeperiod)-1] == ' ':
                    timeperiod = timeperiod[:-1]
            elif item[0] == 'r':
                reason = item[2:]
                if reason[len(reason)-1] == ' ':
                    reason = reason[:-1]
    if timeperiod:
        return time_arg(timeperiod), reason
    return timeperiod, reason

def time_arg(arg):
    '''Given a time argument gets the time in seconds'''
    total = 0
    times = arg.split(' ')
    if len(times) == 0:
        return 0
    #else
    for item in times:
        if item[-1] == 'w':
            total += 7*24*60*60*int(item[:-1])
        elif item[-1] == 'd':
            total += 24*60*60*int(item[:-1])
        elif item[-1] == 'h':
            total += 60*60*int(item[:-1])
        elif item[-1] == 'm':
            total += 60*int(item[:-1])
        elif item[-1] == 's':
            total += int(item[:-1])
    return total
