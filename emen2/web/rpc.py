# $Id$

if __name__ == "__main__":
    # Start the web server directly
    import emen2.web.server
    emen2.web.server.start_rpc()

__version__ = "$Revision$".split(":")[1][:-1].strip()
