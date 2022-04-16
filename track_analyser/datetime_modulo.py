import datetime as dt


class datetime(dt.datetime):
    def __divmod__(self, delta):
        seconds = int((self - dt.datetime.min.replace(tzinfo=dt.timezone.utc)).total_seconds())
        remainder = dt.timedelta(
            seconds=seconds % delta.total_seconds(),
            microseconds=self.microsecond,
        )
        quotient = self - remainder
        return quotient, remainder

    def __floordiv__(self, delta):
        return divmod(self, delta)[0]

    def __mod__(self, delta):
        return divmod(self, delta)[1]
