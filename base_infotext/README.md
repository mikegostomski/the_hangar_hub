# Infotext
Provides the ability to include user-editable text in any site using the base plugin.  
Includes:
-  Template tags for editable text
-  WYSIWYG interface for editing the text

## Quick Start

### Dependencies
The following dependency is REQUIRED and must be installed in your app:
- base

### Configuration
1. Add base-infotext to your INSTALLED_APPS in `settings.py`:
    ```python
    INSTALLED_APPS = [
       ...
       'base',
       'base_infotext',
    ]
    ```
1. Configure your app's top-level `urls.py` to include Infotext views:
    ```python
    urlpatterns = [
        ...
        path('infotext/', include(('base_infotext.urls', 'base_infotext'), namespace='infotext')),
    ]
1. Run migrations: `python manage.py migrate`

## Usage
### Template Tags
The primary purpose of this app is to provide template tags that allow authorized users to 
update text on your site.  For a small amount of text, use the `{%infotext%}` tag.
For a larger amount of text, use the `{%infotext_block%}` tag.  
The following example uses both tags:
```
{% load infotext_taglib %}

<h1>{%infotext code="main_heading" alt="Hello, World!"%}</h1>

{%infotext_block code="example_content"%}
<p>
    This is an example of longer <em>infotext</em><br>
    <ul>
        <li>Bla bla bla</li>
        <li>...</li>
    </ul>
</p>
{%end_infotext_block%}
```

#### Required Attributes:
* **code**: This should uniquely identify the text for the page (url/path)
* **alt**: Alternate (default) text to use when not found in the database  
*(This only applies to the `{%infotext%}` tag. The body of the `{%infotext_block%}` tag is used as the alt text)*

#### Optional Attributes:
* **auto_prefix**: Defaults to True.  When true, the text will be made specific to the page by 
prepending the request path (url) to the **code** attribute.  Set this to False for any text that
is to be displayed on multiple pages (like an error message) to prevent multiple instances of the 
text that may get out-of-sync and display differently on different pages.
* **replacements**: This may be a dict, or string representation of a dict, with the key being the 
text to search for, and the value being the replacement text.
