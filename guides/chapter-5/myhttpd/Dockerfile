FROM ubi8
LABEL description="Creating a custom httpd image"
MAINTAINER Alessandro Rossi <arossi@extraordy.com>
RUN yum install -y httpd
EXPOSE 80
ENV TestVar "This is a test environment variable"
ADD index.html /var/www/html/
COPY index2.html /var/www/html/
USER root
ENTRYPOINT ["/usr/sbin/httpd"]
CMD ["-D", "FOREGROUND"]
