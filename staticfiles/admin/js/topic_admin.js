// admin/js/topic_admin.js
(function($) {
    $(document).ready(function() {
        function toggleEssayField() {
            var type = $('#id_topic_type').val();
            if (type === 'essay') {
                $('#id_essay_topic').closest('.form-row, .form-group, .field-essay_topic').show();
            } else {
                $('#id_essay_topic').closest('.form-row, .form-group, .field-essay_topic').hide();
            }
        }
        toggleEssayField();
        $('#id_topic_type').change(toggleEssayField);
    });
})(django.jQuery);
