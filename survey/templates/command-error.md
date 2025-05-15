Hello {{ USER }},

We were unable to understand your message as you included multiple commands ({{ COMMANDS }}).  Please respond to this comment with only one of the following commands, on its own line.

* `@{{ BOT_NAME }}[bot] CONSENT`
  * If you consent to participate in the study.  After consenting, you will receive at most one comment per day asking for your response.  You can opt out at any time and stop receiving comments.
* `@{{ BOT_NAME }}[bot] OPTOUT`
  * If you would like us to stop sending you comments now and not participate in the study.

{% include "footer.md" %}
