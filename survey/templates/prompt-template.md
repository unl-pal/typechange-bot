I am investigating the reasons developers {{ TYPE }} type annotations on a particular piece of code or a location in code.
Please check the following description of situations a developer {{ TYPE }} a type annotation:

```
{{ RESPONSE }}
```

The code names and descriptions are:

{% for code in codes %} - **{{ code.name }}**: {{ code.description }}
{% endfor %}
Please show which code names best capture the reasons for {{ TYPEING }} a type annotation in a particular spot.
Do not include any commentary.
Use only the described code names.
Include all that are specifically relevant, but no others.
