# moviemeta
A movie meta generator in python. Inspired by https://github.com/praateekmahajan/movie-meta-fetch

This is a command line utility which generates metadata of the movies in directories, using IMDB Api.

Basic usage is simple. Just run this script and open `index.html` in your favourite web browser.

## Useage

### help

`$moviemeta.py -h`

### Mention a directory
*NOTE* - Always mention absolute path to directories. 

`$moviemeta.py -d "C:\movies`

### Sub directories
In some cases, you might not want few directories within your directory to be counted as movies. For example, You might have a directory called **Godfather** having all three godfather series. To mark directories as sub-directories, please add them to `subdir.txt` in comma seperated string format, like:

`godfather,hannibal`
`matrix`

### Sequential requests(Optional)
By default, this program runs in parallel mode. If you want it to run sequentially, pass `-s` switch anytime.

`$moviemeta.py -d "C:\movies" -s`

