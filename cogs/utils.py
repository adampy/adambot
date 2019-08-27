def separate_args(args):
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
