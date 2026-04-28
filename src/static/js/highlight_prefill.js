(function($) {
    'use strict';
    $(document).ready(function() {
        // We use django.jQuery if available, otherwise fallback to $
        var $jq = (typeof django !== 'undefined' && django.jQuery) ? django.jQuery : $;
        
        $jq('#id_contest').change(function() {
            var contestId = $(this).val();
            if (contestId) {
                // Fetch contest details from the API
                $.getJSON('/api/v1/contests/' + contestId + '/', function(data) {
                    if (data.start_time) {
                        var start = new Date(data.start_time);
                        // Format to YYYY-MM-DD (Local time as expected by Django Admin widget)
                        var startDate = start.getFullYear() + '-' + 
                                       ('0' + (start.getMonth() + 1)).slice(-2) + '-' + 
                                       ('0' + start.getDate()).slice(-2);
                        // Format to HH:MM:SS
                        var startTime = ('0' + start.getHours()).slice(-2) + ':' + 
                                       ('0' + start.getMinutes()).slice(-2) + ':' + 
                                       ('0' + start.getSeconds()).slice(-2);
                        
                        $jq('#id_start_time_0').val(startDate);
                        $jq('#id_start_time_1').val(startTime);
                    }
                    if (data.finish_time) {
                        var finish = new Date(data.finish_time);
                        var finishDate = finish.getFullYear() + '-' + 
                                        ('0' + (finish.getMonth() + 1)).slice(-2) + '-' + 
                                        ('0' + finish.getDate()).slice(-2);
                        var finishTime = ('0' + finish.getHours()).slice(-2) + ':' + 
                                        ('0' + finish.getMinutes()).slice(-2) + ':' + 
                                        ('0' + finish.getSeconds()).slice(-2);
                        
                        $jq('#id_finish_time_0').val(finishDate);
                        $jq('#id_finish_time_1').val(finishTime);
                    }
                });
            }
        });
    });
})(jQuery);
