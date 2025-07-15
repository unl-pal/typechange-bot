I am investigating the reasons developers {{ TYPE }} type annotations on  a particular piece of code or a location in code.
Please check the following description of situations a developer {{ TYPE }} a type annotation:

```
{{ RESPONSE }}
```

The coding scheme is:

{% for code in codes %}
 - **{{ code.name }}**: {{ code.description }}
{% endfor %}

Please show which codes best capture the reasons for {{ TYPE }}  a type annotation in a particular spot.
Do not include any commentary.
Show only the exact codes you select, and separate them only with commas.
